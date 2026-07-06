import pytest
from app.database import SessionLocal


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session