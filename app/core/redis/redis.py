# app/core/redis.py
import json
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

import redis
from redis import ConnectionPool
from redis.exceptions import WatchError

from app.config.config import settings

pool = ConnectionPool.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20,
    protocol=2,
)

# Синглтон-клиент для вызова из утилит без Depends
redis_client = redis.Redis(connection_pool=pool)


def get_redis() -> Generator[redis.Redis, None, None]:
    """Dependency для внедрения через Depends(get_redis) в роутерах FastAPI."""
    client = redis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        client.close()


def _get_active_client(client: Optional[redis.Redis]) -> redis.Redis:
    return client if client is not None else redis_client


def write_value(
    name_key: str,
    obj: dict,
    expires_in: int = 300,
    verification_token: Optional[str] = None,
    client: Optional[redis.Redis] = None,
) -> dict[str, Any]:
    """
    Сохраняет объект. Если verification_token не передан, генерирует новый UUID.
    """
    r = _get_active_client(client)
    token = verification_token or str(uuid.uuid4())
    full_key = f"{name_key}:{token}"

    r.setex(
        name=full_key,
        time=expires_in,
        value=json.dumps(obj),
    )
    return {"verification_token": token, "expires_in": expires_in}


def read_value(
    name_key: str,
    verification_token: str,
    client: Optional[redis.Redis] = None,
) -> dict:
    """Читает и десериализует значение по токену."""
    r = _get_active_client(client)
    raw_data = r.get(f"{name_key}:{verification_token}")
    if not raw_data:
        raise ValueError("Срок действия ключа истек или токен недействителен")
    return json.loads(raw_data)


def update_value(
    name_key: str,
    verification_token: str,
    modifier_fn: Callable[[dict], dict],
    max_retries: int = 10,
    retry_delay: float = 0.05,
    client: Optional[redis.Redis] = None,
) -> dict:
    """
    Атомарно модифицирует существующий ключ с защитой от параллельных правок.
    
    Использует optimistic locking (WATCH/MULTI/EXEC).
    modifier_fn — функция-мутатор, принимающая текущий dict и возвращающая измененный dict.
    TTL ключа сохраняется.
    """
    r = _get_active_client(client)
    full_key = f"{name_key}:{verification_token}"

    for attempt in range(max_retries):
        with r.pipeline() as pipe:
            try:
                # Включаем отслеживание ключа
                pipe.watch(full_key)

                raw_data = pipe.get(full_key)
                if not raw_data:
                    pipe.unwatch()
                    raise ValueError("Срок действия ключа истек или токен недействителен")

                current_ttl = pipe.ttl(full_key)
                current_data = json.loads(raw_data)

                # Применяем трансформацию данных
                updated_data = modifier_fn(current_data)

                # Открываем транзакционный буфер
                pipe.multi()

                if current_ttl > 0:
                    pipe.setex(full_key, current_ttl, json.dumps(updated_data))
                else:
                    pipe.set(full_key, json.dumps(updated_data))

                # Применяем: вызовет WatchError, если другой клиент изменил ключ
                pipe.execute()
                return updated_data

            except WatchError:
                # Конфликт с другим клиентом — ждем и повторяем попытку
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Не удалось обновить ключ {full_key} из-за высокой конкуренции ({max_retries} попыток)"
                    )
                time.sleep(retry_delay)


@contextmanager
def redis_lock(
    lock_name: str,
    timeout: int = 10,
    blocking_timeout: int = 5,
    client: Optional[redis.Redis] = None,
):
    """
    Пессимистическая распределенная блокировка для сложных/долгих операций.
    Использование:
        with redis_lock("my_lock_name"):
            ...
    """
    r = _get_active_client(client)
    lock = r.lock(f"lock:{lock_name}", timeout=timeout, blocking_timeout=blocking_timeout)
    acquired = lock.acquire()
    if not acquired:
        raise TimeoutError(f"Не удалось захватить блокировку для {lock_name}")
    try:
        yield
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass


def delete_value(
    name_key: str,
    verification_token: str,
    client: Optional[redis.Redis] = None,
) -> None:
    """Удаляет ключ."""
    r = _get_active_client(client)
    r.delete(f"{name_key}:{verification_token}")


def check_exists(
    name_key: str,
    verification_token: str,
    client: Optional[redis.Redis] = None,
) -> bool:
    """Проверяет существование ключа в Redis."""
    r = _get_active_client(client)
    return bool(r.exists(f"{name_key}:{verification_token}"))


# Пример использования update_value (оптимистическая блокировка):

# Python
# def append_user_action(current_dict: dict) -> dict:
#     current_dict.setdefault("actions_count", 0)
#     current_dict["actions_count"] += 1
#     return current_dict

# # Безопасно вызывать параллельно из разных потоков/процессов/серверов:
# updated = update_value("sms_session", token, modifier_fn=append_user_action)
# Пример использования redis_lock (пессимистическая блокировка для внешних I/O):

# Python
# with redis_lock(f"sms_session:{token}"):
#     data = read_value("sms_session", token)
#     # делаем внешние запросы или долгую работу
#     data["status"] = "processed"
#     write_value("sms_session", data, verification_token=token)