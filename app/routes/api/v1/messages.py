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
    if not data.terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не приняты Условия использования и/или Политика конфиденциальности",
        )

    verification_service = VerificationService(db)
    user_service = UserService(db)

    # 1. Поиск пользователя
    user = user_service.get_user_by_phone(data.phone)
    if not user:
        # user = user_service.find_and_create_user(phone=data.phone)
        raise Exception("Пользователь с таким телефоном не найден!")
    # 2. Проверка проверочного кода (возвращает объект VerificationCode)
    verified_code = verification_service.verify_code(
        code=data.code,
        type=VerificationType.LOGIN,
        user=user,
    )
    if not verified_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или просроченный код",
        )

    # 3. Извлечение сетевых данных клиента
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    user_document_service = UserDocumentService(db)

    # 4. Фиксация согласия с документами через обновленный сервис
    user_document_service.confirm_user_documents(
        user_id=user.id,
        verification_code_id=verified_code.id,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # 5. Отправка сообщений
    message_service = MessageService(db)
    try:
        order = message_service.send_bulk_email_phone(
            sender_phone=user.phone,
            recipients=data.contacts,
            text=data.text,
            sender_user_id=user.id,
            ip_address=client_ip,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # return {
    #     "status": "ok",
    #     "order_uuid": str(order.uuid),
    #     "count": len(order.messages),
    # }
    return LoginApiResponse(
        status_code=0,
        data={"order_id": str(order.uuid)}
    )


@router.post("/bulk-send")
def bulk_send(
    data: BulkSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Массовая отправка авторизованным пользователем."""
    message_service = MessageService(db)
    order = message_service.send_bulk_email_phone(
        sender_phone=current_user.phone,
        recipients=data.contacts,
        text=data.text,
        channel_type=data.channel_type,
        sender_user_id=current_user.id
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
