from app.repositories import user_repo
from app.services.audit_service import audit_service


class UserService:
    async def create_user(self, db, data):
        # only allow valid fields for User model
        allowed_fields = ["name", "email", "role"]

        clean_data = {
            k: v for k, v in data.items()
            if k in allowed_fields
        }

        # validation
        if "email" not in clean_data:
            raise Exception("Email is required")

        existing = await user_repo.get_by_email(
            db,
            clean_data["email"]
        )

        if existing:
            raise Exception("Email already exists")

        user = await user_repo.create(
            db,
            clean_data
        )

        await audit_service.log(
            db,
            "users",
            user.id,
            "create",
            new_values=clean_data
        )

        return user

    async def update_user(self, db, user_id, data):
        old_user = await user_repo.get(db, user_id)

        if not old_user:
            raise Exception("User not found")

        updated = await user_repo.update(
            db,
            user_id,
            data
        )

        await audit_service.log(
            db,
            "users",
            user_id,
            "update",
            old_values={
                "name": old_user.name,
                "email": old_user.email,
                "role": old_user.role
            },
            new_values=data
        )

        return updated

    async def archive_user(self, db, user_id):
        deleted = await user_repo.soft_delete(
            db,
            user_id
        )

        await audit_service.log(
            db,
            "users",
            user_id,
            "archive"
        )

        return deleted


user_service = UserService()