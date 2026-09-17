# app/services/channel_cache.py

import json
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from .redis import redis_client  # или ваш экземпляр Redis
from app.models.models import S_Channel, S_ChannelIdentifier

CACHE_KEY_CHANNELS = "cache:channels_registry"
CACHE_TTL = 86400  # 24 часа


class ChannelCacheService:
    def __init__(self, db: Session):
        self.db = db

    def _fetch_from_db(self) -> List[Dict]:
        """Прямой SQL-запрос для выборки активных каналов и идентификаторов."""
        records = (
            self.db.query(
                S_Channel.id.label("channel_id"),
                S_Channel.code.label("channel_code"),
                S_ChannelIdentifier.id.label("identifier_id"),
                S_ChannelIdentifier.name.label("identifier_name"),
                S_ChannelIdentifier.is_default.label("is_default"),
            )
            .join(S_ChannelIdentifier, S_ChannelIdentifier.channel_id == S_Channel.id)
            .filter(
                S_Channel.is_active.is_(True),
                S_ChannelIdentifier.is_active.is_(True),
            )
            .all()
        )

        return [
            {
                "channel_id": r.channel_id,
                "channel_code": r.channel_code,
                "identifier_id": r.identifier_id,
                "identifier_name": r.identifier_name,
                "is_default": bool(r.is_default),
            }
            for r in records
        ]

    def get_all_channels(self, force_refresh: bool = False) -> List[Dict]:
        """Возвращает все каналы из Redis-кеша (при промахе запрашивает БД)."""
        if not force_refresh:
            cached = redis_client.get(CACHE_KEY_CHANNELS)
            if cached:
                return json.loads(cached)

        # Cache Miss или принудительное обновление:
        data = self._fetch_from_db()
        redis_client.setex(CACHE_KEY_CHANNELS, CACHE_TTL, json.dumps(data))
        return data

    def get_default_by_channel_code(self, channel_code: str) -> Optional[Dict]:
        """Быстрый поиск дефолтного идентификатора по коду канала (phone, email)."""
        channels = self.get_all_channels()
        for item in channels:
            if item["channel_code"] == channel_code and item["is_default"]:
                return item
        return None

    def get_by_identifier_name(self, name: str) -> Optional[Dict]:
        """Поиск по имени идентификатора."""
        channels = self.get_all_channels()
        for item in channels:
            if item["identifier_name"] == name:
                return item
        return None

    def invalidate(self):
        """Инвалидация кеша при изменениях в справочниках админки."""
        redis_client.delete(CACHE_KEY_CHANNELS)