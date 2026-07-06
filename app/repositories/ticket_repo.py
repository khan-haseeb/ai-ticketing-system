from sqlalchemy import select, func

from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.query_builder import TicketQueryBuilder


class TicketRepository(BaseRepository[Ticket]):
    def __init__(self):
        super().__init__(Ticket)

    async def get_by_project(self, db, project_id):
        query = select(Ticket).where(Ticket.project_id == project_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def search_by_title(self, db, title: str):
        """Find tickets whose title contains the given string (case-insensitive)."""
        query = (
            select(Ticket)
            .where(Ticket.archived_at.is_(None))
            .where(func.lower(Ticket.title).contains(title.lower()))
            .order_by(Ticket.created_at.desc())
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def check_assignment_conflict(self, db, ticket_id, new_assignee_id):
        ticket = await self.get(db, ticket_id)
        if not ticket:
            return None
        if ticket.assignee_id and ticket.assignee_id != new_assignee_id:
            query = select(User).where(User.id == ticket.assignee_id)
            result = await db.execute(query)
            current_user = result.scalar_one_or_none()
            return {
                "conflict": True,
                "ticket_id": str(ticket.id),
                "current_assignee": current_user.name,
                "requested_assignee": str(new_assignee_id),
            }
        return None

    async def filter_tickets(self, db, filters):
        query = TicketQueryBuilder.build(filters)
        result = await db.execute(query)
        return result.scalars().all()