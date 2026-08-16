# app/api/v1/messages.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.services.message import MessageService
from app.services.consent import ConsentService
from app.models.models import ChannelType,User
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])

class QuickSendRequest(BaseModel):
    text: str
    channels: List[str]  # ["sms", "email"] или ["both"]
    contacts: List[dict]  # [{"phone": "+7...", "email": "..."}]

class BulkSendRequest(BaseModel):
    text: str
    channels: List[str]
    contacts: List[dict]

class SendSingleRequest(BaseModel):
    recipient_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    text: str
    channels: List[str]

@router.post("/quick-send")
def quick_send(
    data: QuickSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Быстрая отправка (авторизованный пользователь)."""
    # Определяем каналы
    channels_set = set(data.channels)
    if "both" in channels_set:
        channel_type = ChannelType.BOTH
    elif "sms" in channels_set and "email" in channels_set:
        channel_type = ChannelType.BOTH
    elif "sms" in channels_set:
        channel_type = ChannelType.SMS
    elif "email" in channels_set:
        channel_type = ChannelType.EMAIL
    else:
        raise HTTPException(status_code=400, detail="Не выбран ни один канал")

    message_service = MessageService(db)
    # Отправляем массово
    try:
        messages = message_service.send_bulk(
            sender_phone=current_user.phone,
            recipients=data.contacts,
            text=data.text,
            channels=channel_type,
            sender_user_id=current_user.id
        )
        order_id = messages[0].order_id if messages else None
        return {"status": "ok", "order_id": str(order_id), "count": len(messages)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/bulk-send")
def bulk_send(
    data: BulkSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Массовая отправка (аналог quick-send)."""
    return quick_send(data, db, current_user)

@router.get("/history")
def get_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """История отправленных сообщений пользователя."""
    message_service = MessageService(db)
    messages = message_service.get_sender_history(current_user.phone, skip=skip, limit=limit)
    return messages

@router.get("/order/{order_id}")
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статус отправки по order_id (группировка)."""
    message_service = MessageService(db)
    messages = message_service.get_by_order_id(order_id)
    # Проверяем, что пользователь владеет этими сообщениями
    if not messages or messages[0].sender_phone != current_user.phone:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return messages