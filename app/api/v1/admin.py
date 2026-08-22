# app/api/v1/admin.py
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.models import engine, Base, get_db, SessionLocal
import logging
from app.core.config import settings
from app.crud.channel import channel as channel_CRUD
from app.crud.channel_identifier import channel_identifier
from app.schemas.channel import ChannelCreate
from app.schemas.channel_identifier import ChannelIdentifierCreate

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
        # Удаляем все таблицы
        Base.metadata.drop_all(bind=engine)
        logger.info("Все таблицы удалены")

        # СОЗДАЁМ ТАБЛИЦЫ И ВСТАВЛЯЕМ ДАННЫЕ В ОДНОЙ ТРАНЗАКЦИИ
        # Используем connection напрямую, чтобы контролировать транзакцию
        with engine.connect() as conn:
            # Начинаем транзакцию
            with conn.begin():
                # Создаём таблицы
                Base.metadata.create_all(bind=conn)
                logger.info("Таблицы созданы")

                # Теперь вставляем данные через ту же сессию, привязанную к этому connection
                # Создаём сессию, привязанную к нашему connection
                session = Session(bind=conn)
                
                try:
                    # Вставляем начальные данные
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

                    # Сессия закоммитится автоматически при выходе из with conn.begin()
                    # Но можно и явно: session.commit()
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