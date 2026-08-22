# app/api/v1/endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.models import get_db
from app.services.user import UserService
from app.services.verification import VerificationService
from app.services.consent import ConsentService
from app.services.message import MessageService
from app.services.rate_limit import RateLimitService
from app.models.models import ConsentStatus,ChannelType
from app.schemas.message import MessageInDB

router = APIRouter(prefix="/api/v1", tags=["MSGPRO API"])

# --- Schemas для запросов/ответов (можно вынести в отдельные файлы) ---

class PhoneRequest(BaseModel):
    phone: str

class EmailRequest(BaseModel):
    email: str

class SmsCodeRequest(BaseModel):
    phone: str
    code: str

class PasswordLoginRequest(BaseModel):
    phone: str
    password: str

class ConsentRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None

class ConsentUpdateRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    status: ConsentStatus  # allowed или blocked

class ConsentVerifyRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    code: str

class MessageSendRequest(BaseModel):
    recipient_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    text: str
    channels: ChannelType = ChannelType.PHONE

class BulkMessageSendRequest(BaseModel):
    recipients: List[dict]  # [{"phone": "...", "email": "..."}, ...]
    text: str
    channels: ChannelType = ChannelType.PHONE


# --- Эндпоинты для аутентификации (без регистрации) ---

@router.post("/auth/request-sms")
def request_sms_code(request: PhoneRequest, db: Session = Depends(get_db)):
    """
    Запрос СМС-кода для входа или подтверждения.
    Если пользователь с таким телефоном не существует, он будет создан.
    """
    user_service = UserService(db)
    verification_service = VerificationService(db)

    # Проверка лимита на запрос кода (защита от спама)
    rate_limit_service = RateLimitService(db)
    if not rate_limit_service.check_limit(f"sms_code:{request.phone}", limit=5, period=600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышен лимит запросов кода. Попробуйте позже."
        )

    # Проверяем, есть ли пользователь
    user = user_service.get_user_by_phone(request.phone)
    if not user:
        # Создаём нового пользователя
        user = user_service.create_user(phone=request.phone)

    # Генерация и отправка кода
    code = verification_service.generate_code(phone=request.phone, type="login")
    rate_limit_service.increment(f"sms_code:{request.phone}")

    return {"status": "ok", "data": "Код отправлен на указанный номер"}


@router.post("/auth/verify-sms")
def verify_sms_code(request: SmsCodeRequest, db: Session = Depends(get_db)):
    """
    Проверка СМС-кода. Если код верный, пользователь считается авторизованным.
    В ответ возвращается токен (пока просто телефон).
    """
    verification_service = VerificationService(db)
    user_service = UserService(db)

    # Проверяем код
    valid = verification_service.verify_code(phone=request.phone, code=request.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или просроченный код"
        )

    # Получаем пользователя
    user = user_service.get_user_by_phone(request.phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Отмечаем телефон как подтверждённый (опционально)
    # user.is_verified = True  # если хотите
    # user_service.update_user(user, {"is_verified": True})

    # В реальном проекте здесь выдаётся JWT-токен
    # Пока возвращаем phone как идентификатор
    return {
        "status": "ok",
        "data": {
            "user": {
                "id": user.id,
                "phone": user.phone,
                "full_name": user.full_name,
                "is_verified": user.is_verified,
            }
        }
    }


@router.post("/auth/password/login")
def password_login(request: PasswordLoginRequest, db: Session = Depends(get_db)):
    """
    Вход по паролю (если у пользователя есть пароль).
    """
    user_service = UserService(db)
    user = user_service.authenticate(request.phone, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный телефон или пароль"
        )

    # Возвращаем токен (пока заглушка)
    return {
        "status": "ok",
        "data": {
            "user": {
                "id": user.id,
                "phone": user.phone,
                "full_name": user.full_name,
            }
        }
    }


# --- Эндпоинты для управления согласием ---

@router.post("/consent/request")
def request_consent_verification(request: ConsentRequest, db: Session = Depends(get_db)):
    """
    Запрос на подтверждение согласия (запрет или разрешение).
    Отправляет код на указанный телефон или email.
    """
    consent_service = ConsentService(db)
    phone = request.phone
    email = request.email

    if not phone and not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан ни телефон, ни email"
        )

    # Генерируем код
    code = consent_service.request_consent_verification(phone=phone, email=email)

    # Для возврата сообщения
    channel = phone and "СМС" or "email"
    return {"status": "ok", "data": f"Код отправлен на {channel}"}


@router.post("/consent/confirm")
def confirm_consent(request: ConsentVerifyRequest, db: Session = Depends(get_db)):
    """
    Подтверждение согласия после верификации.
    Меняет статус согласия (блокировка или разрешение).
    """
    consent_service = ConsentService(db)

    # Проверяем, что указан телефон или email
    if not request.phone and not request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан ни телефон, ни email"
        )

    # Подтверждаем согласие (по умолчанию статус будет ALLOWED, если не был ранее установлен)
    confirmed = consent_service.confirm_consent(
        phone=request.phone,
        email=request.email,
        code=request.code
    )
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или просроченный код"
        )

    return {"status": "ok", "data": "Согласие подтверждено"}


@router.post("/consent/block")
def block_consent(request: ConsentRequest, db: Session = Depends(get_db)):
    """
    Запретить получение сообщений на указанный контакт.
    Требует подтверждения через код (вызов /consent/request и /consent/confirm).
    """
    consent_service = ConsentService(db)

    if not request.phone and not request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан ни телефон, ни email"
        )

    # Инициируем процесс блокировки: отправляем код
    consent_service.request_consent_verification(phone=request.phone, email=request.email)

    return {"status": "ok", "data": "Код отправлен для подтверждения блокировки"}


@router.post("/consent/allow")
def allow_consent(request: ConsentRequest, db: Session = Depends(get_db)):
    """
    Разрешить получение сообщений на указанный контакт.
    Также требует подтверждения через код.
    """
    consent_service = ConsentService(db)

    if not request.phone and not request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан ни телефон, ни email"
        )

    consent_service.request_consent_verification(phone=request.phone, email=request.email)

    return {"status": "ok", "data": "Код отправлен для подтверждения разрешения"}


@router.get("/consent/status")
def get_consent_status(phone: Optional[str] = None, email: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Получить текущий статус согласия для указанного контакта.
    """
    if not phone and not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан ни телефон, ни email"
        )

    consent_service = ConsentService(db)
    consent = consent_service.get_consent(phone=phone, email=email)
    if not consent:
        # По умолчанию согласие разрешено (если нет записи)
        status = ConsentStatus.ALLOWED
    else:
        status = consent.status

    return {"status": "ok", "data": {"phone": phone, "email": email, "consent": status}}


# --- Эндпоинты для отправки сообщений ---

@router.post("/messages/send")
def send_single_message(
    request: MessageSendRequest,
    sender_phone: str,  # предполагается, что передаётся в заголовке или query
    db: Session = Depends(get_db)
):
    """
    Отправить одно сообщение одному получателю (по телефону или email).
    """
    message_service = MessageService(db)

    if not request.recipient_phone and not request.recipient_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите хотя бы один канал (телефон или email) для получателя"
        )

    try:
        msg = message_service.send_message(
            sender_phone=sender_phone,
            recipient_phone=request.recipient_phone,
            recipient_email=request.recipient_email,
            text=request.text,
            channels=request.channels
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка отправки сообщения"
        )

    return {
        "status": "ok",
        "data": {
            "message_id": msg.id,
            "order_id": str(msg.order_id),
            "status": msg.status
        }
    }


@router.post("/messages/bulk-send")
def send_bulk_messages(
    request: BulkMessageSendRequest,
    sender_phone: str,
    db: Session = Depends(get_db)
):
    """
    Массовая отправка одного текста на несколько получателей.
    Каждый получатель может иметь телефон и/или email.
    """
    message_service = MessageService(db)

    # Проверяем, что есть получатели
    if not request.recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Список получателей пуст"
        )

    # Отправляем
    try:
        messages = message_service.send_bulk(
            sender_phone=sender_phone,
            recipients=request.recipients,
            text=request.text,
            channels=request.channels
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при массовой отправке"
        )

    return {
        "status": "ok",
        "data": {
            "order_id": str(messages[0].order_id) if messages else None,
            "total": len(messages),
            "message_ids": [m.id for m in messages]
        }
    }


@router.get("/messages/history")
def get_message_history(
    sender_phone: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить историю отправленных сообщений для указанного отправителя.
    """
    message_service = MessageService(db)
    messages = message_service.get_sender_history(sender_phone, skip=skip, limit=limit)
    return {
        "status": "ok",
        "data": messages
    }


@router.get("/messages/order/{order_id}")
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db)
):
    """
    Получить статус всех сообщений в одной массовой отправке по order_id.
    """
    message_service = MessageService(db)
    messages = message_service.get_by_order_id(order_id)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ с таким ID не найден"
        )
    return {
        "status": "ok",
        "data": messages
    }


# --- Дополнительный эндпоинт для проверки работоспособности ---

@router.get("/ping")
def ping():
    return {"status": "ok", "message": "pong"}