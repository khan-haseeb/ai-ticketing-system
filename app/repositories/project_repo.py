from sqlalchemy import select

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self):
        super().__init__(Project)

    async def get_by_manager(self, db, manager_id):
        query = select(Project).where(
            Project.manager_id == manager_id
        )

        result = await db.execute(query)
        return result.scalars().all()