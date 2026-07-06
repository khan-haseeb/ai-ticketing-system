import json
import re
from app.agent.llm import ask_llm_with_history

SYSTEM = """You are an intent classifier for a ticketing system.
Classify the user's latest message and return ONLY a JSON object.

Valid intents:
- create_ticket    (user wants to make a new ticket/task/issue)
- create_user      (user wants to add a new user/person/member)
- create_project   (user wants to create a new project)
- query_ticket     (user wants to see/list/show/find tickets)
- query_user       (user wants to see/list/show/find users/people/members)
- query_project    (user wants to see/list/show/find projects)
- update_ticket    (user wants to change/edit/update a ticket)
- update_user      (user wants to change/edit/update a user)
- unknown          (anything else)

CRITICAL RULE — helper_query:
If the user is currently in the middle of a task (e.g. creating a ticket) and asks
a lookup question to help complete that task (like "what projects are available?",
"can you show me the project IDs?", "what users exist?"), this is a HELPER query.
Set "is_helper_query": true. The system will answer the lookup and then automatically
resume the task — do NOT treat this as a context switch.

CRITICAL RULE — continuation, not update:
If there's an active task with fields still open (e.g. creating a ticket that still
needs an assignee, priority, or due date) and the user's message looks like it's just
supplying a value for one of THOSE open fields (e.g. "assign it to Fahad", "make it
high priority", "due next Friday"), classify it as the SAME active intent continuing —
do NOT classify it as update_ticket/update_user. Only use update_* when the user is
clearly referring to an existing, already-created record instead of the one being built.

Return format:
{
  "intent": "<intent_name>",
  "is_helper_query": false
}

If it IS a helper query mid-task:
{
  "intent": "<the_query_intent e.g. query_project>",
  "is_helper_query": true
}

Examples:
"show me all users" (no active task) -> {"intent": "query_user", "is_helper_query": false}
"can you show me available projects?" (while creating a ticket) -> {"intent": "query_project", "is_helper_query": true}
"what project IDs do I have?" (while creating a ticket) -> {"intent": "query_project", "is_helper_query": true}
"list all tickets" -> {"intent": "query_ticket", "is_helper_query": false}
"create a user named Alice" -> {"intent": "create_user", "is_helper_query": false}
"assign it to Fahad" (while creating a ticket, assignee still open) -> {"intent": "create_ticket", "is_helper_query": false}"""

RESUME_PATTERNS = re.compile(
    r"\b(continue|resume|keep going|let'?s finish|finish (that|it|this)|"
    r"what were we doing|where were we|back to (that|the|our))\b",
    re.IGNORECASE,
)

ENTITY_KEYWORDS = {
    "ticket": {"ticket", "issue"},
    "user": {"user", "person", "member", "customer"},
    "project": {"project"},
}


def _pick_resume_target(message: str, workflows: dict) -> str | None:
    keys = list(workflows.keys())
    if len(keys) == 1:
        return keys[0]

    msg_words = set(re.split(r'\W+', message.lower()))
    candidates = []
    for key in keys:
        entity = key.split("_", 1)[-1]
        if ENTITY_KEYWORDS.get(entity, set()) & msg_words:
            candidates.append(key)
    return candidates[0] if len(candidates) == 1 else None


async def classify_intent(state: dict) -> dict:
    session = state.get("session") or {}
    history = session.get("conversation_history", session.get("history", []))
    workflows = session.get("workflows") or {}
    has_active_task = bool(workflows and session.get("active_intent"))

    state["resume_requested"] = False
    state["needs_resume_disambiguation"] = False

    # Deterministic resume-phrase check, bypasses the LLM entirely
    if workflows and RESUME_PATTERNS.search(state["user_message"]):
        target = _pick_resume_target(state["user_message"], workflows)
        if target:
            state["active_intent"] = target
            state["is_helper_query"] = False
            state["helper_query_intent"] = None
            state["resume_requested"] = True
            return state
        else:
            state["needs_resume_disambiguation"] = True
            state["active_intent"] = session.get("active_intent")
            state["is_helper_query"] = False
            state["helper_query_intent"] = None
            return state

    # Build context hint for the LLM
    context_hint = ""
    if has_active_task:
        active = session.get("active_intent", "")
        collected = workflows.get(active, {}).get("collected", {})
        context_hint = (
            f"\n\nCURRENT CONTEXT: The user is in the middle of '{active}'. "
            f"Already collected: {collected}. "
            f"If they ask a lookup question to help complete this task, set is_helper_query=true. "
            f"If they're just supplying a value for a field this task still needs, keep the intent as '{active}'."
        )

    system = SYSTEM + context_hint
    messages = list(history) + [{"role": "user", "content": state["user_message"]}]

    response = await ask_llm_with_history(messages, system)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        data = json.loads(cleaned)
        new_intent = data.get("intent", "unknown")
        is_helper = bool(data.get("is_helper_query", False))
    except (json.JSONDecodeError, KeyError):
        raw = response.strip().lower()
        known = ["create_ticket", "create_user", "create_project",
                 "query_ticket", "query_user", "query_project",
                 "update_ticket", "update_user"]
        new_intent = next((i for i in known if i in raw), "unknown")
        is_helper = False

    # A query mid-task is a helper, not a context switch
    is_query = new_intent.startswith("query_")
    if has_active_task and is_query:
        is_helper = True

    state["active_intent"] = new_intent
    state["is_helper_query"] = is_helper
    state["helper_query_intent"] = new_intent if is_helper else None

    return state