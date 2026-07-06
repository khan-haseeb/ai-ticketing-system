from uuid import UUID
from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class TicketFilter(BaseModel):
    project_id: UUID | None = None
    assignee_id: UUID | None = None
    status: str | None = None
    priority: str | None = None
    overdue_only: bool = False