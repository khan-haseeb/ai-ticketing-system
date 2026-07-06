from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.report_service import report_service


router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"]
)


@router.get("/overdue")
async def overdue_tickets(
    db: AsyncSession = Depends(get_db)
):
    return await report_service.get_overdue_tickets(db)


@router.get("/summary")
async def summary(
    db: AsyncSession = Depends(get_db)
):
    return await report_service.get_summary(db)