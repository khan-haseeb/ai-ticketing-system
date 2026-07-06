"""
execute_tool: runs the actual DB operation or query and returns a human-readable response.

Handles:
- Queries with name-based filtering (e.g. "tickets assigned to Alice")
- Creates (user, ticket, project)
- Updates (ticket, user) with LLM-extracted field resolution
- Helper queries mid-task (paused task context preserved)
"""
import json
import re
from app.services.ticket_service import ticket_service
from app.services.user_service import user_service
from app.services.project_service import project_service
from app.repositories.user_repo import UserRepository
from app.repositories.ticket_repo import TicketRepository
from app.repositories.project_repo import ProjectRepository
from app.database import SessionLocal
from app.agent.llm import ask_llm_with_history
from app.agent.matching import resolve_name

user_repo = UserRepository()
ticket_repo = TicketRepository()
project_repo = ProjectRepository()

SYSTEM = """You are a friendly assistant for a task management system.
Write warm, natural 1-2 sentence responses. Be specific about names and values. Never show UUIDs or raw JSON."""

RESOLVE_SYSTEM = """You are a data extraction helper. Given a user message and session context,
extract update fields and identify what entity the user is referring to.
Return ONLY valid JSON. No explanation."""


# ── Formatters ────────────────────────────────────────────────────────────────

def _format_users(users, for_selection=False):
    if not users:
        return "There are no users yet. You'll need to create one first."
    if for_selection:
        lines = ["Here are the available users:\n"]
        for u in users:
            lines.append(f"• **{u.name}** ({u.email}, {u.role})")
    else:
        lines = [f"Here are all {len(users)} users:\n"]
        for u in users:
            lines.append(f"• **{u.name}** ({u.email}) — role: {u.role}")
    return "\n".join(lines)


def _format_tickets(tickets, for_selection=False):
    if not tickets:
        return "There are no tickets yet."
    if for_selection:
        lines = ["Here are the tickets:\n"]
        for t in tickets:
            lines.append(f"• **{t.title}** — {t.status} / {t.priority}")
    else:
        lines = [f"Here are all {len(tickets)} tickets:\n"]
        for t in tickets:
            due = f", due {t.due_date}" if t.due_date else ""
            lines.append(f"• **{t.title}** — {t.status} / {t.priority}{due}")
    return "\n".join(lines)


def _format_projects(projects, for_selection=False):
    if not projects:
        return "There are no projects yet. You'll need to create one first."
    if for_selection:
        lines = ["Here are the available projects — pick one:\n"]
        for p in projects:
            lines.append(f"• **{p.name}** ({p.status})")
        lines.append("\nJust tell me which project and I'll continue.")
    else:
        lines = [f"Here are all {len(projects)} projects:\n"]
        for p in projects:
            lines.append(f"• **{p.name}** ({p.status})")
    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _humanize(action: str, summary: str, history: list) -> str:
    prompt = f"Action: {action}\nResult: {summary}\nWrite a friendly 1-2 sentence confirmation."
    return await ask_llm_with_history(history + [{"role": "user", "content": prompt}], SYSTEM)


def _is_uuid(value: str) -> bool:
    uuid_re = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_re.match(str(value).strip()))


async def _resolve_target_entity(db, entity_type: str, user_message: str,
                                  session: dict, workflow: dict) -> dict | None:
    """
    Resolves "it"/"this"/"that ticket" style references to a concrete entity,
    checked in order of specificity:
    1. This workflow's own sticky target (persists across interruptions)
    2. The globally most-recently-touched entity (last_entity)
    3. A keyword search fallback against the current message
    """
    target = (workflow or {}).get("target_entity")
    if target and target.get("type") == entity_type:
        return target

    last = session.get("last_entity") or {}
    if last.get("type") == entity_type and last.get("id"):
        return last

    words = [w for w in user_message.split() if len(w) > 3]
    for word in words:
        if entity_type == "ticket":
            matches = await ticket_repo.search_by_title(db, word)
            if matches:
                m = matches[0]
                return {"type": "ticket", "id": str(m.id), "name": m.title}
        else:
            repo = user_repo if entity_type == "user" else project_repo
            all_rows = await repo.list(db)
            matches = [r for r in all_rows if word.lower() in r.name.lower()]
            if matches:
                m = matches[0]
                return {"type": entity_type, "id": str(m.id), "name": m.name}
    return None


async def _extract_update_fields(user_message: str, history: list, entity_type: str) -> dict:
    if entity_type == "ticket":
        prompt = f"""The user wants to update a ticket. Extract the fields they want to change.
User message: "{user_message}"

Possible fields: title, description, status (open/in_progress/review/closed),
priority (low/medium/high/critical), due_date (YYYY-MM-DD format).

Return ONLY a JSON object with the fields to update. Example:
{{"due_date": "2026-06-30", "priority": "high"}}

Only include fields explicitly mentioned. Return {{}} if nothing clear."""
    else:
        prompt = f"""The user wants to update a {entity_type}. Extract update fields from: "{user_message}"
Return ONLY a JSON object."""

    response = await ask_llm_with_history(
        history + [{"role": "user", "content": prompt}],
        RESOLVE_SYSTEM
    )
    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        return json.loads(cleaned)
    except Exception:
        return {}


async def _extract_query_filters(user_message: str, history: list) -> dict:
    """
    Ask the LLM to extract filter intent from a ticket query message.
    Returns dict with optional keys: assignee_name, project_name, status, priority.
    """
    prompt = f"""The user wants to query/list tickets. Extract any filters they mentioned.
User message: "{user_message}"

Return ONLY a JSON object with any of these optional keys:
- assignee_name: person's name they want to filter by (e.g. "Alice")
- project_name: project name to filter by (e.g. "AI Project")
- status: one of open/in_progress/review/closed
- priority: one of low/medium/high/critical

Return {{}} if no filters mentioned (user wants all tickets).
Examples:
"show tickets assigned to Alice" -> {{"assignee_name": "Alice"}}
"open tickets in AI project" -> {{"project_name": "AI Project", "status": "open"}}
"all tickets" -> {{}}"""

    response = await ask_llm_with_history(
        history + [{"role": "user", "content": prompt}],
        RESOLVE_SYSTEM
    )
    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        return json.loads(cleaned)
    except Exception:
        return {}


# ── Main node ─────────────────────────────────────────────────────────────────

async def execute_tool(state: dict) -> dict:
    session = state.get("session") or {}
    history = session.get("conversation_history", session.get("history", []))
    data = state.get("extracted_data", {})
    intent = state.get("active_intent")
    is_helper = state.get("is_helper_query", False)
    user_message = state.get("user_message", "")

    if is_helper:
        intent = state.get("helper_query_intent", intent)

    new_last_entity = None

    try:
        async with SessionLocal() as db:

            # ── QUERIES ───────────────────────────────────────────────────────

            if intent == "query_user":
                users = await user_repo.list(db)
                result_text = _format_users(users, for_selection=is_helper)
                if is_helper:
                    paused = session.get("active_intent", "your task")
                    result_text += f"\n\n*(Still working on **{paused.replace('_', ' ')}** — just pick one above.)*"
                state["final_response"] = result_text

            elif intent == "query_project":
                projects = await project_repo.list(db)
                result_text = _format_projects(projects, for_selection=is_helper)
                if is_helper:
                    paused = session.get("active_intent", "your task")
                    result_text += f"\n\n*(Still working on **{paused.replace('_', ' ')}** — just pick one above.)*"
                state["final_response"] = result_text

            elif intent == "query_ticket":
                # Extract filters from the user's message (name-aware)
                filters = await _extract_query_filters(user_message, list(history))

                assignee_id = None
                project_id = None
                blocked_response = None

                if filters.get("assignee_name"):
                    users = await user_repo.list(db)
                    candidates = [(u.name, str(u.id)) for u in users]
                    result = resolve_name(filters["assignee_name"], candidates)
                    if result.status == "unique":
                        assignee_id = result.uid
                    elif result.status == "ambiguous":
                        names = ", ".join(f"**{n}**" for n, _ in result.candidates)
                        blocked_response = (
                            f"I found more than one user matching \"{filters['assignee_name']}\": "
                            f"{names}. Which one did you mean?"
                        )
                    else:
                        blocked_response = f"I couldn't find a user named \"{filters['assignee_name']}\"."

                if not blocked_response and filters.get("project_name"):
                    projects = await project_repo.list(db)
                    candidates = [(p.name, str(p.id)) for p in projects]
                    result = resolve_name(filters["project_name"], candidates)
                    if result.status == "unique":
                        project_id = result.uid
                    elif result.status == "ambiguous":
                        names = ", ".join(f"**{n}**" for n, _ in result.candidates)
                        blocked_response = (
                            f"I found more than one project matching \"{filters['project_name']}\": "
                            f"{names}. Which one did you mean?"
                        )
                    else:
                        blocked_response = f"I couldn't find a project named \"{filters['project_name']}\"."

                if blocked_response:
                    state["final_response"] = blocked_response
                else:
                    # Build filter dict for the repo
                    repo_filters = {}
                    if assignee_id:
                        repo_filters["assignee_id"] = assignee_id
                    if project_id:
                        repo_filters["project_id"] = project_id
                    if filters.get("status"):
                        repo_filters["status"] = filters["status"]
                    if filters.get("priority"):
                        repo_filters["priority"] = filters["priority"]

                    if repo_filters:
                        tickets = await ticket_repo.filter_tickets(db, repo_filters)
                    else:
                        tickets = await ticket_repo.list(db)

                    state["final_response"] = _format_tickets(tickets)

            # ── CREATE ────────────────────────────────────────────────────────

            elif intent == "create_user":
                result = await user_service.create_user(db, data)
                new_last_entity = {"type": "user", "id": str(result.id), "name": result.name}
                summary = f"Created user '{result.name}' ({result.email}), role: {result.role}."
                state["final_response"] = await _humanize("create user", summary, list(history))
                state["extracted_data"] = {}

            elif intent == "create_ticket":
                result = await ticket_service.create_ticket(db, data)
                new_last_entity = {"type": "ticket", "id": str(result.id), "name": result.title}
                summary = f"Created ticket '{result.title}', priority {result.priority}, status {result.status}."
                state["final_response"] = await _humanize("create ticket", summary, list(history))
                state["extracted_data"] = {}

            elif intent == "create_project":
                result = await project_service.create_project(db, data)
                new_last_entity = {"type": "project", "id": str(result.id), "name": result.name}
                summary = f"Created project '{result.name}'."
                state["final_response"] = await _humanize("create project", summary, list(history))
                state["extracted_data"] = {}

            # ── UPDATE TICKET ─────────────────────────────────────────────────

            elif intent == "update_ticket":
                workflow = (session.get("workflows") or {}).get("update_ticket", {})
                target = await _resolve_target_entity(db, "ticket", user_message, session, workflow)
                if not target:
                    tickets = await ticket_repo.list(db)
                    if tickets:
                        state["final_response"] = (
                            "Which ticket would you like to update?\n\n"
                            + _format_tickets(tickets, for_selection=True)
                        )
                    else:
                        state["final_response"] = "There are no tickets yet. Would you like to create one?"
                else:
                    update_fields = await _extract_update_fields(user_message, list(history), "ticket")
                    if not update_fields:
                        state["target_entity"] = target
                        state["awaiting_followup"] = True
                        state["final_response"] = (
                            f"I found **{target['name']}**. What would you like to change? "
                            f"(e.g. due date, priority, status)"
                        )
                    else:
                        updated = await ticket_service.update_ticket(db, target["id"], update_fields)
                        new_last_entity = {"type": "ticket", "id": str(updated.id), "name": updated.title}
                        changes = ", ".join(f"{k}={v}" for k, v in update_fields.items())
                        summary = f"Updated ticket '{updated.title}': {changes}."
                        state["final_response"] = await _humanize("update ticket", summary, list(history))
                        state["extracted_data"] = {}

            # ── UPDATE USER ───────────────────────────────────────────────────

            elif intent == "update_user":
                workflow = (session.get("workflows") or {}).get("update_user", {})
                target = await _resolve_target_entity(db, "user", user_message, session, workflow)
                user_id = data.pop("user_id", None) or (target.get("id") if target else None)
                if not user_id:
                    state["final_response"] = "Which user would you like to update?"
                else:
                    update_fields = await _extract_update_fields(user_message, list(history), "user")
                    if not update_fields and not data:
                        state["target_entity"] = target or {"type": "user", "id": user_id}
                        state["awaiting_followup"] = True
                        state["final_response"] = "What would you like to change for this user?"
                    else:
                        result = await user_service.update_user(db, user_id, update_fields or data)
                        new_last_entity = {"type": "user", "id": str(result.id), "name": result.name}
                        state["final_response"] = await _humanize(
                            "update user", f"Updated user {result.name}.", list(history)
                        )
                        state["extracted_data"] = {}

            else:
                state["final_response"] = (
                    "I can help you **create** or **show** tickets, users, and projects, "
                    "or **update** existing ones. What would you like to do?"
                )

    except Exception as e:
        err = str(e)
        if "Email already exists" in err:
            state["final_response"] = "That email is already registered. Would you like to use a different one?"
        elif "Email is required" in err:
            state["final_response"] = "I need an email address to create this user. What email should I use?"
        elif "not found" in err.lower():
            state["final_response"] = "I couldn't find that record. Could you double-check and try again?"
        else:
            state["final_response"] = f"Something went wrong: {err}. Please try again."

    if new_last_entity:
        state["new_last_entity"] = new_last_entity

    return state