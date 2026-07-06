from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.common import TicketFilter

from app.api.deps import get_db
from app.services.ticket_service import ticket_service
from app.repositories import ticket_repo

from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    AssignTicket
)


router = APIRouter(
    prefix="/api/v1/tickets",
    tags=["Tickets"]
)


@router.post("/", response_model=TicketResponse)
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db)
):
    return await ticket_service.create_ticket(
        db,
        payload.model_dump()
    )


@router.get("/")
async def list_tickets(
    project_id: UUID | None = None,
    assignee_id: UUID | None = None,
    status: str | None = None,
    priority: str | None = None,
    overdue_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    filters = TicketFilter(
        project_id=project_id,
        assignee_id=assignee_id,
        status=status,
        priority=priority,
        overdue_only=overdue_only
    )

    return await ticket_repo.filter_tickets(
        db,
        filters
    )


@router.post("/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: UUID,
    payload: AssignTicket,
    db: AsyncSession = Depends(get_db)
):
    return await ticket_service.assign_ticket(
        db,
        ticket_id,
        payload.assignee_id
    )