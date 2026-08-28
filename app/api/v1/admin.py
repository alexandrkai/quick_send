# app/api/v1/admin.py
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.models import engine, Base, get_db, SessionLocal,create_engine,text
import logging
from app.core.config import settings
from app.crud.channel import channel as channel_CRUD
from app.crud.feedback import feedback
from app.crud.channel_identifier import channel_identifier
from app.schemas.channel import ChannelCreate
from app.schemas.channel_identifier import ChannelIdentifierCreate
from sqlalchemy.exc import OperationalError
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/reset-db")
async def reset_database(db: Session = Depends(get_db)):
    """
    Пересоздаёт все таблицы в базе данных.
    ВНИМАНИЕ: все данные будут потеряны! Используйте только в разработке.
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    try:
        # --- 1. Проверяем существование базы данных и создаём, если нет ---
        db_url = settings.DATABASE_URL
        parsed = urlparse(db_url)
        db_name = parsed.path.lstrip('/')
        # Строка подключения без указания базы (для подключения к postgres/template1)
        admin_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}/postgres"
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

        with admin_engine.connect() as admin_conn:
            # Проверка существования базы
            result = admin_conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :dbname"), {"dbname": db_name})
            exists = result.fetchone()
            if not exists:
                # Создаём базу
                admin_conn.execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"База данных '{db_name}' создана")

        admin_engine.dispose()

        # --- 2. Теперь подключаемся к созданной базе и выполняем операции ---
        # Удаляем все таблицы
        Base.metadata.drop_all(bind=engine)
        logger.info("Все таблицы удалены")

        # Создаём таблицы и вставляем данные в одной транзакции
        with engine.connect() as conn:
            with conn.begin():
                Base.metadata.create_all(bind=conn)
                logger.info("Таблицы созданы")

                session = Session(bind=conn)
                try:
                    phone_channel = channel_CRUD.create(session, obj_in=ChannelCreate(code="phone"))
                    channel_identifier.create(
                        session,
                        obj_in=ChannelIdentifierCreate(
                            channel_id=phone_channel.id,
                            field_name="phone",
                            validation_regex=r"^\+7\(?\d{3}\)?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}$"
                        )
                    )

                    email_channel = channel_CRUD.create(session, obj_in=ChannelCreate(code="email"))
                    channel_identifier.create(
                        session,
                        obj_in=ChannelIdentifierCreate(
                            channel_id=email_channel.id,
                            field_name="email",
                            validation_regex=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
                        )
                    )

                    logger.info("Начальные данные добавлены")
                except Exception as e:
                    logger.error(f"Ошибка при вставке данных: {e}")
                    raise
                finally:
                    session.close()

        return {"status": "ok", "message": "База данных успешно пересоздана"}

    except Exception as e:
        logger.error(f"Ошибка при пересоздании БД: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при пересоздании БД: {str(e)}"
        )

@router.get("/feedbacks")
async def get_feedbacks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user) # позже добавим авторизацию
):
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="Доступ запрещён")
    feedbacks = feedback.get_multi(db, skip=skip, limit=limit)
    return feedbacks