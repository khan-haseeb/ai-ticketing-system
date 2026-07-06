from uuid import UUID
from datetime import datetime, date

from pydantic import BaseModel


class TicketCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: UUID
    assignee_id: UUID | None = None
    priority: str = "medium"
    due_date: date | None = None


class AssignTicket(BaseModel):
    assignee_id: UUID


class TicketResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: str
    priority: str
    project_id: UUID
    assignee_id: UUID | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True