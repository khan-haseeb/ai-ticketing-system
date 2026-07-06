from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, AuditMixin


class User(Base, UUIDMixin, TimestampMixin, AuditMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(50),
        default="member"
    )