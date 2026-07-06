from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    manager_id: UUID


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    manager_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True