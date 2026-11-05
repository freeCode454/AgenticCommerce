"""
Redis 客户端连接池封装
"""

import redis.asyncio as redis
from app.conf.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_redis():
    return redis_client
