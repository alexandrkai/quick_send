from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
import pytest

from app.models.models import (
    Base,
    Contact,
    PermissionProhibition,
    PermissionProhibitionStatus,
    PermissionProhibitionType,
    S_Channel,
    S_ChannelIdentifier,
    VerificationCode,
    VerificationType,
)

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        # Базовая инициализация справочников
        channel = S_Channel(code="phone", description="Phone SMS")
        db.add(channel)
        db.flush()

        identifier = S_ChannelIdentifier(
            channel_id=channel.id,
            name="mobile_phone",
            is_default=True,
            is_active=True,
        )
        db.add(identifier)
        db.commit()

        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def phone_identifier(db_session):
    return db_session.query(S_ChannelIdentifier).filter_by(name="mobile_phone").first()