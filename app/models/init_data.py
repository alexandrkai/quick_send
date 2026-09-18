import json
import logging
import os
from urllib.parse import urlparse
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from app.config.config import settings
from app.crud.channel import crud_channel
from app.crud.channel_identifier import crud_channel_identifier
from app.crud.document import crud_document
from app.models.models import (
    Base,
    MessageTemplate,
    SessionLocal,
    UserDocumentType,
    engine,
)
from app.schemas import ChannelCreate, ChannelIdentifierCreate, DocumentCreate

logger = logging.getLogger(__name__)

# Конфигурация дефолтных системных шаблонов по коду канала
DEFAULT_SYSTEM_TEMPLATES = {
    "phone": {
        "name": "Системный SMS шаблон по умолчанию",
        "title_template": "От {author_phone}: ",
        "body_template": "{text}",
        "footer_template": "\nОтписаться: {opt_out_url}",
    },
    "email": {
        "name": "Системный Email шаблон по умолчанию",
        "title_template": "Сообщение от {author_name}",
        "body_template": "{text}",
        "footer_template": "\n---\nЕсли вы не хотите получать рассылку: {opt_out_url}",
    },
}


def __init_channels_and_channel_identifiers() -> None:
    """Инициализация каналов, их полей идентификаторов и системных шаблонов по умолчанию."""
    path_file = os.path.join(settings.PATH_DATA_DIR, "init", "s_channel.json")
    if not os.path.exists(path_file):
        logger.warning(f"Файл {path_file} не найден.")
        return

    with open(path_file, "r", encoding="utf-8") as file:
        data = json.loads(file.read())

    with SessionLocal() as db:
        try:
            for item in data:
                code = item.get("code")
                name = item.get("name") or item.get("description", code)

                channel = crud_channel.create(
                    db,
                    obj_in=ChannelCreate(code=code, description=name),
                )

                for identifier_data in item.get("identifiers", []):
                    identifier = crud_channel_identifier.create(
                        db,
                        obj_in=ChannelIdentifierCreate(
                            channel_id=channel.id,
                            name=identifier_data["name"],
                            validation_regex=identifier_data.get("validation_regex"),
                            is_default=True,
                        ),
                    )

                    # Создаем системный шаблон по умолчанию для данного канала
                    tpl_config = DEFAULT_SYSTEM_TEMPLATES.get(code)
                    if tpl_config:
                        template = MessageTemplate(
                            channel_identifier_id=identifier.id,
                            user_id=None,  # Системный дефолт
                            name=tpl_config["name"],
                            title_template=tpl_config["title_template"],
                            body_template=tpl_config["body_template"],
                            footer_template=tpl_config["footer_template"],
                            is_default=True,
                            is_active=True,
                        )
                        db.add(template)

            db.commit()
            logger.info("Справочники каналов, идентификаторов и системные шаблоны инициализированы.")
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при вставке каналов и шаблонов: {e}")
            raise


def __init_documents() -> None:
    """Инициализация активных версий юридических документов."""
    with SessionLocal() as db:
        try:
            for doc in UserDocumentType:
                path_file = os.path.join(
                    settings.PATH_DATA_DIR, "init", f"{doc.value}.html"
                )
                if not os.path.exists(path_file):
                    logger.warning(f"Файл шаблона {path_file} не найден.")
                    continue

                with open(path_file, "r", encoding="utf-8") as file:
                    content = file.read()

                title = (
                    "Условия использования"
                    if doc == UserDocumentType.TERMS
                    else "Политика конфиденциальности"
                )

                crud_document.create(
                    db,
                    obj_in=DocumentCreate(
                        doc_type=doc.value,
                        version="1.0",
                        title=title,
                        content=content,
                        is_active=True,
                    ),
                )
            logger.info("Юридические документы успешно инициализированы.")
        except Exception as e:
            logger.error(f"Ошибка при вставке документов: {e}")
            raise


def init_db() -> dict:
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    try:
        # 1. Проверяем существование базы данных и создаём, если её нет
        db_url = settings.DATABASE_URL
        parsed = urlparse(db_url)
        db_name = parsed.path.lstrip("/")

        admin_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}/postgres"
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

        with admin_engine.connect() as admin_conn:
            result = admin_conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name},
            )
            if not result.fetchone():
                admin_conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info(f"База данных '{db_name}' создана")

        admin_engine.dispose()

        # 2. Полный сброс схемы public
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("DROP SCHEMA public CASCADE;"))
                conn.execute(text("CREATE SCHEMA public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        logger.info("Схема public полностью очищена (CASCADE)")

        # 3. Создание актуальных таблиц
        Base.metadata.create_all(bind=engine)
        logger.info("Таблицы успешно созданы")

        # 4. Наполнение начальными данными
        __init_channels_and_channel_identifiers()
        __init_documents()

        return {"status": "ok", "message": "База данных успешно пересоздана"}

    except Exception as e:
        logger.error(f"Ошибка при пересоздании БД: {e}")
        raise HTTPException(
            status_code=500, detail=f"Ошибка при пересоздании БД: {str(e)}"
        )