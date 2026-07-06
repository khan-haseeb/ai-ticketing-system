from datetime import date
from sqlalchemy import select

from app.models.ticket import Ticket


class TicketQueryBuilder:
    @staticmethod
    def build(filters):
        query = select(Ticket).where(
            Ticket.archived_at.is_(None)
        )

        if filters.project_id:
            query = query.where(
                Ticket.project_id == filters.project_id
            )

        if filters.assignee_id:
            query = query.where(
                Ticket.assignee_id == filters.assignee_id
            )

        if filters.status:
            query = query.where(
                Ticket.status == filters.status
            )

        if filters.priority:
            query = query.where(
                Ticket.priority == filters.priority
            )

        if filters.overdue_only:
            query = query.where(
                Ticket.due_date < date.today()
            )

        return query