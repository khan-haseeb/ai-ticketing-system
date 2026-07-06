import pytest

from app.repositories import user_repo


@pytest.mark.asyncio
async def test_create_user(db):
    user = await user_repo.create(
        db,
        {
            "name": "Haseeb",
            "email": "haseeb@test.com",
            "role": "admin"
        }
    )

    assert user.id is not None
    assert user.name == "Haseeb"