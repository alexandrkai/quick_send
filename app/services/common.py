from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    Contact,
    Message,
    MessageStatus,
    S_Channel,
    S_ChannelIdentifier,
    VerificationCode,
)


def get_sent_sms_count_for_recent_period(
    db: Session,
    *,
    hours: int = 1,
    user_id: Optional[int] = None,
) -> Dict[str, int]:
    """
    Считает отправленные SMS за последние N часов (по умолчанию 1 час):
    - VerificationCode: сервисные коды (по каналу phone)
    - Message: рассылки в статусах SENT и DELIVERED (по каналу phone)
    """
    time_threshold = datetime.now() - timedelta(hours=hours)

    # 1. Подсчет кодов верификации за период
    # Если VerificationCode привязан к Contact:
    vc_query = (
        db.query(func.count(VerificationCode.id))
        .join(Contact, Contact.id == VerificationCode.contact_id)
        .join(S_ChannelIdentifier, S_ChannelIdentifier.id == Contact.channel_identifier_id)
        .join(S_Channel, S_Channel.id == S_ChannelIdentifier.channel_id)
        .filter(
            S_Channel.code == "phone",
            VerificationCode.created_at >= time_threshold,
        )
    )
    if user_id is not None:
        vc_query = vc_query.filter(Contact.user_id == user_id)

    vc_count = vc_query.scalar() or 0

    # 2. Подсчет сообщений рассылок в статусах SENT/DELIVERED за период
    target_statuses = [
        getattr(MessageStatus.SENT, "value", MessageStatus.SENT),
        getattr(MessageStatus.DELIVERED, "value", MessageStatus.DELIVERED),
    ]

    msg_query = (
        db.query(func.count(Message.id))
        .join(S_ChannelIdentifier, S_ChannelIdentifier.id == Message.channel_identifier_id)
        .join(S_Channel, S_Channel.id == S_ChannelIdentifier.channel_id)
        .filter(
            S_Channel.code == "phone",
            Message.status.in_(target_statuses),
            Message.created_at >= time_threshold,
        )
    )
    if user_id is not None:
        msg_query = msg_query.filter(Message.user_id == user_id)

    msg_count = msg_query.scalar() or 0

    return {
        "period_hours": hours,
        "since": time_threshold.isoformat(),
        "verification_codes_count": vc_count,
        "messages_count": msg_count,
        "total_sms_sent": vc_count + msg_count,
    }