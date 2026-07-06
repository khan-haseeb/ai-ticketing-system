from typing import TypedDict, Optional


class AgentState(TypedDict):
    session_id: str
    session: dict
    user_message: str
    active_intent: Optional[str]
    extracted_data: dict
    missing_fields: list[str]
    final_response: Optional[str]
    is_helper_query: bool           # True = lookup mid-task, resume after answering
    helper_query_intent: Optional[str]  # the query intent to execute as a helper
    resume_requested: bool              # deterministic resume-phrase matched a paused workflow
    needs_resume_disambiguation: bool   # 2+ paused workflows, couldn't tell which to resume
    needs_clarification: Optional[dict]  # {"field","status":"ambiguous"|"none","query","options"?}
    target_entity: Optional[dict]       # entity this turn resolved as the update target
    awaiting_followup: bool             # update_* flow found its target but is waiting on fields
