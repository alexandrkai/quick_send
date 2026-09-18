from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from .web import *
from app.core.cache.channel_memory_cache import channel_cache
from app.models.models import (
    Contact,
    Message,
    MessageStatus,
    S_Channel,
    S_ChannelIdentifier,
    VerificationCode,VerificationType
)


def get_sent_sms_count_for_recent_period(
    db: Session,
    *,
    user_id: int,
    seconds: int = 3600,
) -> Dict[str, int]:
    """
    Считает количество отправленных SMS конкретного пользователя за последние N секунд:
    - VerificationCode: сервисные SMS входа (VerificationType.LOGIN)
    - Message: сообщения рассылки по каналу phone в статусах SENT и DELIVERED
    """
    time_threshold = datetime.utcnow() - timedelta(seconds=seconds)

    # 1. Сервисные SMS-коды входа конкретного пользователя
    vc_count = (
        db.query(func.count(VerificationCode.id))
        .filter(
            VerificationCode.user_id == user_id,
            VerificationCode.type == VerificationType.LOGIN,
            VerificationCode.created_at >= time_threshold,
        )
        .scalar()
    ) or 0

    # 2. Идентификатор телефонного канала берем из памяти (без лишних JOIN в БД)
    phone_channel = channel_cache.get_default_by_channel(db, channel_code="phone")
    phone_identifier_id = phone_channel["identifier_id"] if phone_channel else None

    # 3. Сообщения рассылок (строго отправленные или доставленные)
    msg_query = db.query(func.count(Message.id)).filter(
        Message.user_id == user_id,
        Message.status.notin_([MessageStatus.FAILED]),
        Message.created_at >= time_threshold,
    )

    if phone_identifier_id:
        msg_query = msg_query.filter(Message.channel_identifier_id == phone_identifier_id)

    msg_count = msg_query.scalar() or 0

    return {
        "user_id": user_id,
        "seconds": seconds,
        "verification_codes_count": vc_count,
        "messages_count": msg_count,
        "total_sms_sent": vc_count + msg_count,
    }