from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.project_service import project_service
from app.repositories import project_repo

from app.schemas.project import (
    ProjectCreate,
    ProjectResponse
)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"]
)


@router.post("/", response_model=ProjectResponse)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    return await project_service.create_project(
        db,
        payload.model_dump()
    )


@router.get("/")
async def list_projects(
    db: AsyncSession = Depends(get_db)
):
    return await project_repo.list(db)