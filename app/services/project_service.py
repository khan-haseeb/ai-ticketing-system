from app.repositories import project_repo, user_repo
from app.services.audit_service import audit_service


class ProjectService:
    async def create_project(self, db, data):
        manager = await user_repo.get(
            db,
            data["manager_id"]
        )

        if not manager:
            raise Exception("Manager not found")

        project = await project_repo.create(
            db,
            data
        )

        await audit_service.log(
            db,
            "projects",
            project.id,
            "create",
            new_values=data
        )

        return project


project_service = ProjectService()