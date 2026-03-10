import json
import redis
from typing import Optional, Any
from datetime import datetime
from backend.app.config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB,
    DASHBOARD_CACHE_TTL,
    MONTHLY_CACHE_TTL
)

class CacheService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True
        )

    def get_dashboard_key(self, company_code: str, date: str) -> str:
        return f"dashboard:{date}:{company_code}"

    def get_monthly_key(self, company_code: str, year: int, month: int, module: str) -> str:
        return f"monthly:{year}:{month}:{company_code}:{module}"

    def get(self, key: str) -> Optional[Any]:
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    def set(self, key: str, data: Any, ttl: int):
        self.redis_client.setex(key, ttl, json.dumps(data))

    def delete(self, key: str):
        self.redis_client.delete(key)
        
    def delete_pattern(self, pattern: str):
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)

cache_service = CacheService()

def get_cache_service():
    return cache_service
