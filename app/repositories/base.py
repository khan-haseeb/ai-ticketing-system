from datetime import datetime
from typing import Generic, TypeVar, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, record_id):
        query = select(self.model).where(self.model.id == record_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def list(self, db: AsyncSession):
        query = select(self.model).where(
            self.model.archived_at.is_(None)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def create(self, db: AsyncSession, data: dict):
        instance = self.model(**data)

        db.add(instance)
        await db.commit()
        await db.refresh(instance)

        return instance

    async def update(self, db: AsyncSession, record_id, data: dict):
        instance = await self.get(db, record_id)

        if not instance:
            return None

        for key, value in data.items():
            setattr(instance, key, value)

        await db.commit()
        await db.refresh(instance)

        return instance

    async def soft_delete(self, db: AsyncSession, record_id):
        instance = await self.get(db, record_id)

        if not instance:
            return None

        instance.archived_at = datetime.utcnow()

        await db.commit()
        await db.refresh(instance)

        return instance