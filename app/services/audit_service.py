from app.repositories.base import BaseRepository
from app.models.audit_log import AuditLog


audit_repo = BaseRepository(AuditLog)


class AuditService:
    async def log(
        self,
        db,
        table_name,
        record_id,
        operation,
        old_values=None,
        new_values=None
    ):
        return await audit_repo.create(
            db,
            {
                "table_name": table_name,
                "record_id": str(record_id),
                "operation": operation,
                "old_values": old_values,
                "new_values": new_values
            }
        )


audit_service = AuditService()