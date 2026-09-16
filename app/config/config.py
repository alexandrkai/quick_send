# app/core/config.py

from functools import lru_cache
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import sys,json
from pydantic import model_validator

# Корень проекта (2 уровня вверх от текущего файла: config.py -> core -> app -> ROOT)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


class Settings(BaseSettings):
    # _instance: Optional["Settings"] = None

    # def __new__(cls, *args, **kwargs):
    #     if cls._instance is None:
    #         cls._instance = super().__new__(cls)
    #     return cls._instance

    PATH_ROOT_DIR: str = str(BASE_DIR)
    PATH_CONFIG_DIR: str = os.path.join(PATH_ROOT_DIR, "app", "config")
    PATH_DATA_DIR: str = os.path.join(PATH_ROOT_DIR, "app", "data")
    # --- База данных и кэш ---
    DATABASE_URL: str = "postgresql://kai:291297@192.168.1.222:5432/quick"
    REDIS_URL: str = "redis://:291297@192.168.1.222:6379/0"

    # --- Безопасность и токены ---
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней

    PERIOD_VALIDATED_SMS_CODE_SECONDS: int = 5*60
    # --- Провайдеры и окружение ---
    SMS_PROVIDER: str = "dummy"
    EMAIL_PROVIDER: str = "dummy"
    DEBUG: bool = True

    

    # --- SMTP конфигурация ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your_email@gmail.com"
    SMTP_PASSWORD: str = "your_app_password"
    ADMIN_EMAIL: str = "info@msgpro.ru"

    # --- Бизнес-правила и лимиты ---
    LIMIT_PERIOD_HOURS: int = 1
    LIMIT_COUNT_SMS_FOR_LIMIT_PERIOD_HOURS: int = 10
    
    # --- Регулярные выражения валидации ---
    PHONE_VALIDATION_REGEX: str = r"^\+7\(?\d{3}\)?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}$"
    # "^[^@\s]+@[^@\s]+\.[^@\s]+$"
    EMAIL_VALIDATION_REGEX: str = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # extra="ignore",  # Игнорировать лишние переменные в .env
        extra="allow",  # Разрешает и сохраняет любые дополнительные переменные из .env
    )
    
    @model_validator(mode="after")
    def load_json_data(self) -> "Settings":
        # Если файл существует, подгружаем его содержимое в поле self.JSON_DATA
        JSON_REDIS_CONFIG_PATH=os.path.join(self.PATH_CONFIG_DIR,"redis.json")
        if os.path.exists(JSON_REDIS_CONFIG_PATH):
            with open(JSON_REDIS_CONFIG_PATH, "r", encoding="utf-8") as f:
                self.REDISS = json.load(f)
        return self


# --- Реализация Singleton ---

@lru_cache
def get_settings() -> Settings:
    """
    Возвращает единственный экземпляр настроек (Singleton).
    Благодаря @lru_cache чтение .env и инициализация выполняются ровно 1 раз.
    """
    return Settings()


# Для обратной совместимости с прямым импортом (from app.core.config import settings)
settings: Settings = get_settings()
