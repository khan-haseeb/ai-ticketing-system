import redis.asyncio as redis
from app.config import settings


redis_client = redis.from_url(settings.redis_url)


async def get_redis():
    yield redis_client