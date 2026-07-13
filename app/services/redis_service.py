import logging
from typing import Any, Optional
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisService:
    """
    Singleton service for Redis interactions.
    Provides async helper methods for idempotency checks.
    """
    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        if not self.redis:
            logger.info("Connecting to Redis...")
            self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # Verify connection
            await self.redis.ping()
            logger.info("Connected to Redis successfully.")

    async def disconnect(self) -> None:
        if self.redis:
            logger.info("Disconnecting from Redis...")
            await self.redis.close()
            self.redis = None
            logger.info("Disconnected from Redis.")

    async def get(self, key: str) -> Optional[str]:
        if not self.redis:
            await self.connect()
        assert self.redis is not None
        return await self.redis.get(key)

    async def set(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> None:
        if not self.redis:
            await self.connect()
        assert self.redis is not None
        await self.redis.set(key, value, ex=expire_seconds)

    async def delete(self, key: str) -> None:
        if not self.redis:
            await self.connect()
        assert self.redis is not None
        await self.redis.delete(key)

    async def set_if_not_exists(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        """
        Set a key to a value only if it does not already exist.
        Returns True if the key was set, False if the key already existed.
        """
        if not self.redis:
            await self.connect()
        assert self.redis is not None
        # nx=True ensures the key is only set if it does not exist
        return await self.redis.set(key, value, ex=expire_seconds, nx=True)

redis_service = RedisService()
