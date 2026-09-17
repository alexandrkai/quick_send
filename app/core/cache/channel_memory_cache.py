# app/core/channel_memory_cache.py

from datetime import datetime, timedelta
import threading
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.models import S_Channel, S_ChannelIdentifier


class ChannelMemoryCache:
    _instance: Optional["ChannelMemoryCache"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._registry: List[Dict[str, Any]] = []
                    cls._instance._by_channel_default: Dict[str, Dict[str, Any]] = {}
                    cls._instance._by_identifier_name: Dict[str, Dict[str, Any]] = {}
                    cls._instance._expires_at: Optional[datetime] = None
                    cls._instance._ttl = timedelta(hours=12)
        return cls._instance

    def _is_expired(self) -> bool:
        return self._expires_at is None or datetime.utcnow() >= self._expires_at

    def refresh(self, db: Session) -> None:
        """Принудительно перечитывает БД и обновляет in-memory словари."""
        with self._lock:
            records = (
                db.query(
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

            new_registry = []
            new_defaults = {}
            new_by_name = {}

            for r in records:
                item = {
                    "channel_id": r.channel_id,
                    "channel_code": r.channel_code,
                    "identifier_id": r.identifier_id,
                    "identifier_name": r.identifier_name,
                    "is_default": bool(r.is_default),
                }
                new_registry.append(item)
                new_by_name[item["identifier_name"]] = item

                # Индексируем дефолтный идентификатор для каждого канала (phone, email)
                if item["is_default"]:
                    new_defaults[item["channel_code"]] = item

            self._registry = new_registry
            self._by_channel_default = new_defaults
            self._by_identifier_name = new_by_name
            self._expires_at = datetime.utcnow() + self._ttl

    def _ensure_fresh(self, db: Session) -> None:
        if self._is_expired():
            self.refresh(db)

    def get_all(self, db: Session) -> List[Dict[str, Any]]:
        """Возвращает весь список каналов."""
        self._ensure_fresh(db)
        return list(self._registry)

    def get_default_by_channel(self, db: Session, channel_code: str) -> Optional[Dict[str, Any]]:
        """O(1) поиск дефолтного идентификатора (например, для 'phone' или 'email')."""
        self._ensure_fresh(db)
        return self._by_channel_default.get(channel_code)

    def get_by_identifier_name(self, db: Session, name: str) -> Optional[Dict[str, Any]]:
        """O(1) поиск по названию идентификатора."""
        self._ensure_fresh(db)
        return self._by_identifier_name.get(name)

    def clear(self) -> None:
        """Инвалидация кеша (вызывать при изменениях в админке)."""
        with self._lock:
            self._expires_at = None


channel_cache = ChannelMemoryCache()
"""
Прогрев кеша при старте приложения (main.py)

Чтобы первый запрос пользователя не ждал обращения к базе данных, кеш наполняется во время старта FastAPI через lifespan:
Python

# main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.channel_memory_cache import channel_cache
from app.models.models import SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Предзагрузка каналов в память при старте
    db = SessionLocal()
    try:
        channel_cache.refresh(db)
        print("[CACHE] Справочник каналов и идентификаторов успешно загружен в память.")
    finally:
        db.close()
    yield


app = FastAPI(lifespan=lifespan)

3. Пример использования в коде (quick_send / MessageService)

Теперь получение identifier_id происходит мгновенно без обращений к PostgreSQL:
Python

from app.core.channel_memory_cache import channel_cache

# Получение дефолтного SMS-канала
channel_info = channel_cache.get_default_by_channel(db, channel_code="phone")
if not channel_info:
    raise ValueError("Канал phone не сконфигурирован в системе")

# Доступны все запрошенные поля:
print(channel_info["channel_id"])       # 1
print(channel_info["channel_code"])     # "phone"
print(channel_info["identifier_id"])    # 1
print(channel_info["identifier_name"])  # "mobile_phone"
print(channel_info["is_default"])       # True

4. Сброс (инвалидация) при изменении в админке

Если администратор обновил запись в S_Channel или S_ChannelIdentifier, достаточно вызвать:
Python

from app.core.channel_memory_cache import channel_cache

@router.put("/admin/channels/{id}")
def update_channel(..., db: Session = Depends(get_db)):
    # 1. Сохранили изменения в БД
    # ...
    # 2. Сбросили кеш в памяти
    channel_cache.clear()
    return {"status": "ok"}
"""