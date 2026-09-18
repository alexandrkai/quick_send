import logging
import time,sys,os
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config.config import settings
from app.models.models import MessageStatus

# Корень проекта (2 уровня вверх от текущего файла: config.py -> core -> app -> ROOT)
BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    connect_args={"options": "-c timezone=Europe/Moscow"}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

BATCH_SIZE = getattr(settings, "WORKER_BATCH_SIZE", 10)
POLL_INTERVAL = getattr(settings, "WORKER_POLL_INTERVAL", 1.0)
MAX_RETRIES = getattr(settings, "MAX_MESSAGE_RETRIES", 3)

logging.basicConfig(level=logging.INFO, format="[%(process)d] %(message)s")


# --- Шлюзы отправки ---

def send_sms_gateway(phone: str, text_content: str) -> bool:
    time.sleep(0.1)
    logging.info(f"[SMS GATEWAY] Отправлено на {phone}")
    return True


def send_email_gateway(email: str, text_content: str) -> bool:
    time.sleep(0.1)
    logging.info(f"[EMAIL GATEWAY] Отправлено на {email}")
    return True


def route_and_dispatch(channel_code: str, recipient: str, text_content: str) -> bool:
    if channel_code == "phone":
        return send_sms_gateway(recipient, text_content)
    elif channel_code == "email":
        return send_email_gateway(recipient, text_content)
    else:
        raise ValueError(f"Неподдерживаемый канал доставки: {channel_code}")


# --- Захват сообщений из БД ---

def fetch_and_lock_batch(session, batch_size: int):
    """
    Атомарно блокирует сообщения со статусом PENDING.
    Выбирает также текущее значение repeat_counter.
    """
    sql = text("""
        WITH cte AS (
            SELECT id
            FROM messages
            WHERE status = :pending_status
            ORDER BY id ASC
            LIMIT :batch_size
            FOR UPDATE SKIP LOCKED
        )
        UPDATE messages m
        SET status = :sent_status,
            updated_at = NOW()
        FROM cte
        JOIN messages orig_m ON orig_m.id = cte.id
        JOIN s_channel_identifiers sci ON sci.id = orig_m.channel_identifier_id
        JOIN s_channels sc ON sc.id = sci.channel_id
        WHERE m.id = cte.id
        RETURNING m.id, m.recipient_value, m.text, m.repeat_counter, sc.code AS channel_code;
    """)
    return session.execute(
        sql,
        {
            "batch_size": batch_size,
            "pending_status": MessageStatus.PENDING.value,
            "sent_status": MessageStatus.SENT.value,
        }
    ).fetchall()


# --- Основной цикл воркера с обработкой ретраев ---

def run_worker_loop():
    logging.info(f"Воркер запущен. Лимит повторов (MAX_RETRIES): {MAX_RETRIES}")

    while True:
        session = SessionLocal()
        try:
            messages = fetch_and_lock_batch(session, BATCH_SIZE)
            session.commit()

            if not messages:
                session.close()
                time.sleep(POLL_INTERVAL)
                continue

            logging.info(f"Взято в работу сообщений: {len(messages)}")

            for msg_id, recipient, text_content, repeat_counter, channel_code in messages:
                try:
                    success = route_and_dispatch(channel_code, recipient, text_content)
                    if not success:
                        raise RuntimeError("Шлюз вернул статус неуспешной отправки")

                    # Успех: фиксируем DELIVERED
                    session.execute(
                        text("""
                            UPDATE messages
                            SET status = :status,
                                delivered_at = :delivered_at,
                                error_message = NULL,
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {
                            "status": MessageStatus.DELIVERED.value,
                            "delivered_at": datetime.now(),
                            "id": msg_id,
                        }
                    )
                    session.commit()

                except Exception as exc:
                    err_msg = str(exc)
                    current_attempts = (repeat_counter or 0) + 1

                    if current_attempts < MAX_RETRIES:
                        # Возвращаем в PENDING для повторной обработки другим воркером или позже
                        logging.warning(
                            f"[RETRY] Сообщение ID {msg_id} сбой (попытка {current_attempts}/{MAX_RETRIES}): {err_msg}"
                        )
                        session.execute(
                            text("""
                                UPDATE messages
                                SET status = :status,
                                    repeat_counter = :counter,
                                    error_message = :error,
                                    updated_at = NOW()
                                WHERE id = :id
                            """),
                            {
                                "status": MessageStatus.PENDING.value,
                                "counter": current_attempts,
                                "error": f"[Retry {current_attempts}] {err_msg}",
                                "id": msg_id,
                            }
                        )
                    else:
                        # Попытки исчерпаны: окончательный FAILED
                        logging.error(
                            f"[FAILED] Сообщение ID {msg_id} исчерпало лимит ретраев ({MAX_RETRIES}): {err_msg}"
                        )
                        session.execute(
                            text("""
                                UPDATE messages
                                SET status = :status,
                                    repeat_counter = :counter,
                                    error_message = :error,
                                    updated_at = NOW()
                                WHERE id = :id
                            """),
                            {
                                "status": MessageStatus.FAILED.value,
                                "counter": current_attempts,
                                "error": f"[Max retries exceeded] {err_msg}",
                                "id": msg_id,
                            }
                        )

                    session.commit()

        except Exception as ex:
            session.rollback()
            logging.error(f"Ошибка цикла обработки воркера: {ex}")
            time.sleep(1.0)
        finally:
            session.close()


if __name__ == "__main__":
    run_worker_loop()