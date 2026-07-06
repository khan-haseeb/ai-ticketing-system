from datetime import datetime

from sqlalchemy import String, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_log"

    table_name: Mapped[str] = mapped_column(String(100))
    record_id: Mapped[str] = mapped_column(String(255))
    operation: Mapped[str] = mapped_column(String(50))
    old_values: Mapped[dict | None] = mapped_column(JSON)
    new_values: Mapped[dict | None] = mapped_column(JSON)


class SessionStore(Base):
    __tablename__ = "session_store"

    session_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True
    )

    state: Mapped[dict] = mapped_column(JSON)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )