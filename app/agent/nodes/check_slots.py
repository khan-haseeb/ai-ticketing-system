"""
Slot checker: identifies which required fields are still missing after extraction
and entity resolution, then asks the user for exactly one field at a time.

Key improvements over original:
- Accepts project/user names (resolution happens in resolve_entities node)
- Asks human-friendly questions that don't mention UUIDs
- Shows available options inline when asking for project/user
"""
from app.agent.llm import ask_llm_with_history
from app.database import SessionLocal
from app.repositories.project_repo import ProjectRepository
from app.repositories.user_repo import UserRepository

project_repo = ProjectRepository()
user_repo = UserRepository()

REQUIRED_FIELDS = {
    "create_ticket": ["title", "project_id"],
    "create_user": ["name", "email"],
    "create_project": ["name"],
}

SYSTEM = """You are a friendly assistant for a ticketing system.
Ask for exactly ONE missing piece of information at a time, in a natural conversational tone.
Be brief and friendly. Do not list multiple questions at once."""


async def _get_project_options() -> str:
    try:
        async with SessionLocal() as db:
            projects = await project_repo.list(db)
            if projects:
                names = ", ".join(f"**{p.name}**" for p in projects)
                return f" Available projects: {names}."
    except Exception:
        pass
    return ""


async def _get_user_options() -> str:
    try:
        async with SessionLocal() as db:
            users = await user_repo.list(db)
            if users:
                names = ", ".join(f"**{u.name}**" for u in users)
                return f" Available users: {names}."
    except Exception:
        pass
    return ""


async def check_slots(state: dict) -> dict:
    clarification = state.get("needs_clarification")
    if clarification:
        field = clarification["field"]
        state["missing_fields"] = list(dict.fromkeys(
            [field] + (state.get("missing_fields") or [])
        ))
        if clarification["status"] == "ambiguous":
            names = ", ".join(f"**{n}**" for n, _ in clarification["options"])
            state["final_response"] = (
                f"I found more than one match for \"{clarification['query']}\": {names}. "
                f"Which one did you mean?"
            )
        else:
            state["final_response"] = (
                f"I couldn't find anyone/anything matching \"{clarification['query']}\". "
                f"Could you double-check the name, or tell me how you'd like to proceed?"
            )
        return state

    intent = state.get("active_intent")
    needed = REQUIRED_FIELDS.get(intent, [])
    collected = state.get("extracted_data", {})

    missing = [f for f in needed if f not in collected or not collected[f]]
    state["missing_fields"] = missing

    if not missing:
        return state

    next_field = missing[0]
    session = state.get("session") or {}
    # Support both key names for history
    history = session.get("conversation_history", session.get("history", []))
    already_have = {k: v for k, v in collected.items() if v}

    # Build a context-aware question hint
    if next_field == "project_id":
        options = await _get_project_options()
        question_hint = f"Which project should this belong to? Just tell me the project name.{options}"
    elif next_field in ("assignee_id", "manager_id"):
        options = await _get_user_options()
        label = "manager" if next_field == "manager_id" else "assignee"
        question_hint = f"Who should be the {label}? You can use their name.{options}"
    elif next_field == "title":
        question_hint = "What should the ticket title be?"
    elif next_field == "name":
        question_hint = "What's the name?"
    elif next_field == "email":
        question_hint = "What's the email address?"
    else:
        question_hint = f"What is the {next_field.replace('_', ' ')}?"

    prompt = f"""The user wants to {intent.replace('_', ' ')}.
We already have: {already_have if already_have else 'nothing yet'}.
We need to ask for: {next_field}
Suggested question: "{question_hint}"

Write a short, friendly, natural message asking just for the {next_field}.
Do NOT mention UUIDs or IDs — just ask for the name or value naturally."""

    messages = list(history) + [{"role": "user", "content": state["user_message"]}]
    response = await ask_llm_with_history(messages, prompt)
    state["final_response"] = response.strip()

    return state