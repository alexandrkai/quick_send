# app/services/rate_limit.py
import redis
from sqlalchemy.orm import Session
from app.core.config import settings

class RateLimitService:
    def __init__(self, db: Session):
        self.db = db
        self.redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def check_limit(self, key: str, limit: int = 10, period: int = 3600) -> bool:
        """Проверяет, не превышен ли лимит для ключа за период (в секундах)."""
        current = self.redis.get(f"rate_limit:{key}")
        if current is None:
            return True
        return int(current) < limit

    def increment(self, key: str, period: int = 3600):
        """Увеличивает счётчик для ключа."""
        self.redis.incr(f"rate_limit:{key}")
        self.redis.expire(f"rate_limit:{key}", period)