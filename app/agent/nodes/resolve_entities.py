"""
Entity resolution node: converts user-provided names into UUIDs before slot checking.

When a user says "AI Project" instead of a UUID, this node:
1. Detects which fields need resolution (project_id, assignee_id, manager_id)
2. Fetches the real entities from the database
3. Matches the name the user provided against real names via resolve_name()
4. Updates extracted_data with the resolved UUID, or flags the field for
   clarification if the match was ambiguous (multiple candidates) or absent

This eliminates the "please provide the project ID" loop for clear cases, while
surfacing genuine ambiguity ("which Fahad?") instead of silently guessing.
"""
import re
from app.database import SessionLocal
from app.repositories.project_repo import ProjectRepository
from app.repositories.user_repo import UserRepository
from app.repositories.ticket_repo import TicketRepository
from app.agent.matching import resolve_name
from app.agent.nodes.extract_slots import SLOT_SCHEMAS

project_repo = ProjectRepository()
user_repo = UserRepository()
ticket_repo = TicketRepository()


def _is_uuid(value: str) -> bool:
    """Check if a string is already a UUID."""
    uuid_re = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_re.match(str(value).strip()))


def _flag_clarification(state: dict, field: str, query: str, result) -> None:
    if state.get("needs_clarification"):
        return  # only surface the first ambiguity per turn
    if result.status == "ambiguous":
        state["needs_clarification"] = {
            "field": field, "status": "ambiguous", "query": query,
            "options": result.candidates,
        }
    else:
        state["needs_clarification"] = {"field": field, "status": "none", "query": query}


async def resolve_entities(state: dict) -> dict:
    """
    Resolves name-based references to UUIDs in extracted_data.
    Also scans the full conversation history for entity names.
    """
    data = state.get("extracted_data", {})
    session = state.get("session", {})
    history = session.get("history", session.get("conversation_history", []))
    user_message = state.get("user_message", "")

    # Fields the *current* intent's schema actually declares. Guessing a field
    # from conversation text is only safe when the active intent uses that
    # field at all - otherwise a name/project mentioned in passing can leak
    # into a payload the target model doesn't have a column for (e.g.
    # manager_id ending up on a ticket).
    schema = SLOT_SCHEMAS.get(state.get("active_intent"))
    schema_fields = set(schema.get("required", []) + schema.get("optional", [])) if schema else set()

    # Build a combined text corpus to search for entity mentions
    all_text = user_message + " " + " ".join(
        m.get("content", "") for m in history if m.get("role") == "user"
    )

    needs_project = "project_id" in (state.get("missing_fields") or []) or \
                    not data.get("project_id") or \
                    (data.get("project_id") and not _is_uuid(str(data.get("project_id", ""))))

    needs_user_ref = any(
        (f in (state.get("missing_fields") or []) or
         (data.get(f) and not _is_uuid(str(data.get(f, "")))))
        for f in ["assignee_id", "manager_id", "user_id"]
    )

    try:
        async with SessionLocal() as db:
            # ── Resolve project reference ──────────────────────────────────
            if needs_project:
                current_val = data.get("project_id", "")
                if current_val and not _is_uuid(str(current_val)):
                    projects = await project_repo.list(db)
                    candidates = [(p.name, str(p.id)) for p in projects]
                    result = resolve_name(str(current_val), candidates)
                    if result.status == "unique":
                        data["project_id"] = result.uid
                    else:
                        data.pop("project_id", None)
                        _flag_clarification(state, "project_id", str(current_val), result)

                elif not current_val and "project_id" in schema_fields:
                    # Try to find a project name mentioned anywhere in conversation
                    projects = await project_repo.list(db)
                    if projects:
                        candidates = [(p.name, str(p.id)) for p in projects]
                        for name, uid in candidates:
                            if name.lower() in all_text.lower():
                                data["project_id"] = uid
                                break

            # ── Resolve user references (assignee, manager) ────────────────
            if needs_user_ref:
                users = await user_repo.list(db)
                user_candidates = [(u.name, str(u.id)) for u in users] + \
                                  [(u.email, str(u.id)) for u in users]

                for field in ["assignee_id", "manager_id", "user_id"]:
                    current_val = data.get(field, "")
                    if current_val and not _is_uuid(str(current_val)):
                        result = resolve_name(str(current_val), user_candidates)
                        if result.status == "unique":
                            data[field] = result.uid
                        else:
                            data.pop(field, None)
                            _flag_clarification(state, field, str(current_val), result)
                    elif not current_val and field in schema_fields:
                        # Try to detect a user name mentioned in THIS message only
                        # (not the full history blob - matching against a long
                        # multi-turn corpus causes spurious word-overlap hits,
                        # e.g. every "*.com" email sharing the token "com").
                        # Ambiguous/no-match here is not surfaced as a question -
                        # this is an opportunistic scan, not a field the user was
                        # necessarily asked to fill.
                        result = resolve_name(user_message, user_candidates)
                        if result.status == "unique":
                            data[field] = result.uid

    except Exception:
        # Resolution failure is non-fatal — slot checking will ask the user
        pass

    state["extracted_data"] = data
    return state
