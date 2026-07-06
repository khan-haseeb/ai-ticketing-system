from datetime import date

from sqlalchemy import String, Text, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, AuditMixin


class Ticket(Base, UUIDMixin, TimestampMixin, AuditMixin):
    __tablename__ = "tickets"

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="open"
    )

    priority: Mapped[str] = mapped_column(
        String(50),
        default="medium"
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id")
    )

    assignee_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )


class TicketLink(Base, UUIDMixin):
    __tablename__ = "ticket_links"

    source_ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id")
    )

    target_ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id")
    )

    link_type: Mapped[str] = mapped_column(
        String(50)
    )