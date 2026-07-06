import pytest
from app.services.user_service import user_service


@pytest.mark.asyncio
async def test_create_user_service(db):
    user = await user_service.create_user(
        db,
        {
            "name": "Haseeb",
            "email": "haseeb2@test.com",
            "role": "admin"
        }
    )

    assert user.email == "haseeb@test.com"