from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.user_service import user_service
from app.repositories import user_repo

from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse
)


router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"]
)


@router.post("/", response_model=UserResponse)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    return await user_service.create_user(
        db,
        payload.model_dump()
    )


@router.get("/")
async def list_users(
    db: AsyncSession = Depends(get_db)
):
    return await user_repo.list(db)


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await user_repo.get(db, user_id)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    return await user_service.update_user(
        db,
        user_id,
        payload.model_dump(exclude_unset=True)
    )


@router.delete("/{user_id}")
async def archive_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await user_service.archive_user(
        db,
        user_id
    )