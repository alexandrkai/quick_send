from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.models.models import User, VerificationType, get_db
from app.schemas.schemas import QuickSendRequest, BulkSendRequest, LoginApiResponse
from app.services.message import MessageService
from app.services.user import UserService
from app.services.verification import VerificationService
from app.services.user_document import UserDocumentService
from app.core.dependencies import get_current_user, get_current_user_from_httponly_cookies
from app.core.redis.redis import *

router = APIRouter(prefix="/messages", tags=["messages"])


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("/quick-send")
def quick_send(
    data: QuickSendRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        service=MessageService(db)
        return service.send_phone_email(data,client_ip,user_agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/bulk-send")
def bulk_send(
    data: BulkSendRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Массовая отправка авторизованным пользователем."""
    client_ip = get_client_ip(request)
    message_service = MessageService(db)
    order = message_service.send_bulk_email_phone(
        sender_phone=current_user.phone,
        recipients=data.contacts,
        text=data.text,
        sender_user_id=current_user.id,
        ip_address=client_ip,
    )
    return {
        "status": "ok",
        "order_uuid": str(order.uuid),
        "count": len(order.messages)
    }


@router.get("/history")
def get_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """История отправленных сообщений пользователя."""
    message_service = MessageService(db)
    return message_service.get_sender_history(current_user.phone, skip=skip, limit=limit)


@router.get("/order/{order_id}")
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статус отправки заказа по его UUID или ID."""
    message_service = MessageService(db)
    messages = message_service.get_by_order_id(order_id)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    # Проверка прав: авторство через user_id или номер отправителя
    first_msg = messages[0]
    if first_msg.user_id != current_user.id and first_msg.order.sender_identifier != current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещен")

    return messages


@router.post("/count-send-sms",summary="Определяет количество отправленных смс за последний промежуток времени с учетом лимита")
def count_send_sms(
    phone: str,
    db: Session = Depends(get_db),
):
    try:
        user_service=UserService(db)
        user=user_service.get_user_by_phone(phone)
        from app.services.common.common import get_sent_sms_count_for_recent_period
        return get_sent_sms_count_for_recent_period(db,user_id=user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))