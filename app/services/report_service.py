from datetime import date
from sqlalchemy import select, func

from app.models.ticket import Ticket
from app.models.project import Project
from app.models.user import User


class ReportService:
    async def get_overdue_tickets(self, db):
        query = select(Ticket).where(
            Ticket.due_date < date.today(),
            Ticket.status != "closed"
        )

        result = await db.execute(query)
        return result.scalars().all()

    async def get_summary(self, db):
        total_users = await db.scalar(
            select(func.count(User.id))
        )

        total_projects = await db.scalar(
            select(func.count(Project.id))
        )

        total_tickets = await db.scalar(
            select(func.count(Ticket.id))
        )

        open_tickets = await db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.status == "open"
            )
        )

        return {
            "total_users": total_users,
            "total_projects": total_projects,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets
        }


report_service = ReportService()