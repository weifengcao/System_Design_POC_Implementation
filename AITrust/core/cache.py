import json
import hashlib
from typing import Optional, Any, Dict
from redis import asyncio as redis_async

from .config import get_settings

settings = get_settings()


class CacheClient:
    """Thin async wrapper around Redis used for quick verdict lookups."""

    def __init__(self):
        self._redis = redis_async.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    @staticmethod
    def build_key(raw_text: str) -> str:
        digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return f"trust:verdict:{digest}"

    async def get_verdict(self, text: str) -> Optional[Dict[str, Any]]:
        key = self.build_key(text)
        payload = await self._redis.get(key)
        if not payload:
            return None
        return json.loads(payload)

    async def set_verdict(self, text: str, data: Dict[str, Any], ttl_seconds: int = 600) -> None:
        key = self.build_key(text)
        await self._redis.set(key, json.dumps(data), ex=ttl_seconds)


cache_client = CacheClient()
