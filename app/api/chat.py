"""
Chat API endpoint.

Key responsibilities:
- Session lifecycle (create / get / delete)
- Running the LangGraph agent graph per message
- Persisting each in-progress workflow (keyed by intent) correctly between turns,
  so collected fields for one workflow are never wiped by activity on another
- Injecting live DB schema into session context on first message
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.session_manager import session_manager
from app.agent.graph import app_graph

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str


async def _get_schema_context() -> str:
    """
    Build a short plain-text description of live DB entities to inject into
    the LLM system context. Gives the model awareness of real project/user names.
    """
    try:
        from app.database import SessionLocal
        from app.repositories.project_repo import ProjectRepository
        from app.repositories.user_repo import UserRepository
        async with SessionLocal() as db:
            projects = await ProjectRepository().list(db)
            users = await UserRepository().list(db)

        project_lines = [f"- {p.name} (id: {p.id}, status: {p.status})" for p in projects]
        user_lines = [f"- {u.name} <{u.email}> (role: {u.role}, id: {u.id})" for u in users]

        return (
            "CURRENT DATABASE STATE:\n"
            f"Projects ({len(projects)}):\n" + ("\n".join(project_lines) or "  (none)") + "\n\n"
            f"Users ({len(users)}):\n" + ("\n".join(user_lines) or "  (none)")
        )
    except Exception:
        return ""


@router.post("/session")
async def create_session():
    session_id = await session_manager.create_session()
    return {"session_id": session_id}


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    await session_manager.delete_session(session_id)
    return {"message": "Session cleared"}


@router.post("/")
async def chat(payload: ChatRequest):
    session = await session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Create a session first.")

    # Inject live schema context on the first message of a session
    if not session.get("schema_context"):
        schema_ctx = await _get_schema_context()
        if schema_ctx:
            await session_manager.update_session(payload.session_id, {"schema_context": schema_ctx})
            session["schema_context"] = schema_ctx

    # Add user message and refresh session (triggers compression if needed)
    await session_manager.add_message(payload.session_id, "user", payload.message)
    session = await session_manager.get_session(payload.session_id)

    # Build LLM-ready history (includes history_summary prepended if compressed)
    llm_history = session_manager.build_history_for_llm(session)

    # Merge schema context into session so nodes can read it
    session_with_history = {**session, "conversation_history": llm_history}

    # Build the agent state, starting from whichever workflow is currently focused
    active_intent = session.get("active_intent")
    workflows = session.get("workflows") or {}
    current_workflow = workflows.get(active_intent) or {}
    already_collected = current_workflow.get("collected", {})

    state = {
        "session_id": payload.session_id,
        "session": session_with_history,
        "user_message": payload.message,
        "active_intent": active_intent,
        "extracted_data": already_collected,
        "missing_fields": current_workflow.get("missing", []),
        "final_response": None,
        "is_helper_query": False,
        "helper_query_intent": None,
        "resume_requested": False,
        "needs_resume_disambiguation": False,
        "needs_clarification": None,
        "target_entity": current_workflow.get("target_entity"),
        "awaiting_followup": False,
        "new_last_entity": None,
    }

    result = await app_graph.ainvoke(state)
    response_text = result.get("final_response") or "I'm not sure how to respond to that."

    # Persist assistant reply
    await session_manager.add_message(payload.session_id, "assistant", response_text)

    is_helper = result.get("is_helper_query", False)
    missing = result.get("missing_fields", [])
    collected = result.get("extracted_data", {})
    intent = result.get("active_intent")
    needs_resume_disambiguation = bool(result.get("needs_resume_disambiguation"))
    needs_clarification = bool(result.get("needs_clarification"))
    awaiting_followup = bool(result.get("awaiting_followup"))
    target_entity = result.get("target_entity")
    new_last_entity = result.get("new_last_entity")

    session_updates = {}
    workflows = dict(session.get("workflows") or {})

    if new_last_entity:
        session_updates["last_entity"] = new_last_entity

    if is_helper or needs_resume_disambiguation:
        # Helper query answered, or the user is being asked which paused
        # workflow to resume — no stored workflow's data changes.
        pass
    elif intent in (None, "unknown"):
        pass
    elif missing or needs_clarification or awaiting_followup:
        # Still collecting fields for `intent` — whether brand-new, a
        # same-intent continuation, or a resumed workflow. Only THIS intent's
        # entry is touched; any other in-progress workflow is left alone.
        workflows[intent] = {
            "collected": collected,
            "missing": missing,
            "target_entity": target_entity or workflows.get(intent, {}).get("target_entity"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        session_updates["workflows"] = workflows
        session_updates["active_intent"] = intent
    else:
        # `intent`'s workflow completed and executed this turn — remove just
        # it, then hand focus to whichever paused workflow was touched most
        # recently (if any).
        workflows.pop(intent, None)
        session_updates["workflows"] = workflows
        session_updates["active_intent"] = next(reversed(workflows), None)

    if session_updates:
        await session_manager.update_session(payload.session_id, session_updates)

    return {"response": response_text, "session_id": payload.session_id}