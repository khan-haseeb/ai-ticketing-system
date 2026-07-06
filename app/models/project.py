from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, AuditMixin


class Project(Base, UUIDMixin, TimestampMixin, AuditMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="active"
    )

    manager_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class ProjectMember(Base, UUIDMixin):
    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id")
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id")
    )

    role: Mapped[str] = mapped_column(
        String(50),
        default="member"
    )