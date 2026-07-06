import json
from app.agent.llm import ask_llm_with_history

SLOT_SCHEMAS = {
    "create_user": {
        "required": ["name", "email"],
        "optional": ["role"],
        "prompt": """Extract user details from the conversation.
Fields:
- name: full name (string, required)
- email: valid email address (string, required)
- role: one of 'admin', 'member', 'viewer' (string, optional, default 'member')

IMPORTANT: Only include a field if the user actually provided it.
If the user said "create user Ali" — only return {"name": "Ali"}.
Do NOT include email or role unless explicitly given.

Return ONLY a JSON object with the fields actually mentioned.""",
    },
    "create_ticket": {
        "required": ["title", "project_id"],
        "optional": ["description", "assignee_id", "priority", "due_date"],
        "prompt": """Extract ticket details from the conversation.
Fields:
- title: ticket title (string, required)
- project_id: if the user mentioned a project name (like "AI Project", "Backend"), put that NAME here as-is.
  A separate step will convert it to a UUID. Only leave it out if no project was mentioned at all.
- description: optional description
- assignee_id: if the user mentioned someone's name to assign to, put that NAME here as-is.
- priority: one of 'low', 'medium', 'high', 'critical' (optional)
- due_date: ISO date string YYYY-MM-DD (optional)

IMPORTANT: Only include a field if the user actually provided that value.
Return ONLY a JSON object with the fields actually mentioned.""",
    },
    "create_project": {
        "required": ["name"],
        "optional": ["description", "manager_id"],
        "prompt": """Extract project details from the conversation.
Fields:
- name: project name (string, required)
- description: optional project description
- manager_id: if the user mentioned a manager name, put that NAME here as-is.

IMPORTANT: Only include a field if the user actually provided that value.
Return ONLY a JSON object with the fields actually mentioned.""",
    },
}


async def extract_slots(state: dict) -> dict:
    intent = state.get("active_intent")
    schema = SLOT_SCHEMAS.get(intent)

    if not schema:
        return state

    session = state.get("session") or {}
    history = session.get("conversation_history", session.get("history", []))

    # Start from what was already collected in this session
    workflows = session.get("workflows") or {}
    already_collected = workflows.get(intent, {}).get("collected", {})

    messages = list(history) + [{"role": "user", "content": state["user_message"]}]

    for _ in range(3):
        response = await ask_llm_with_history(messages, schema["prompt"])
        try:
            cleaned = response.strip().strip("```json").strip("```").strip()
            newly_extracted = json.loads(cleaned)

            # Only accept non-null, non-empty values
            valid_new = {
                k: v for k, v in newly_extracted.items()
                if v is not None and v != "" and k in (schema["required"] + schema["optional"])
            }

            # Merge with what was already collected
            merged = {**already_collected, **valid_new}

            state["extracted_data"] = merged
            return state
        except json.JSONDecodeError:
            continue

    # Fallback: keep what was already collected
    state["extracted_data"] = already_collected
    return state