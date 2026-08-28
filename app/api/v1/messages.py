# app/api/v1/messages.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.models.models import get_db
from app.services.message import MessageService
from app.services.consent import ConsentService
from app.models.models import ChannelType,User
from app.core.dependencies import get_current_user,get_current_user_optional

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
async def quick_send(
    data: QuickSendRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    service = MessageService(db)
    try:
        order = service.send_bulk(
            sender_phone=current_user.phone if current_user else data.sender_phone,
            recipients=data.contacts,
            text=data.text,
            channel_type=data.channel_type,
            sender_user_id=current_user.id if current_user else None
        )
        return {"status": "ok", "order_uuid": str(order.uuid), "count": len(order.messages)}
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