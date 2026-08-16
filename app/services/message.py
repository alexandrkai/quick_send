# app/services/message.py
import uuid
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.crud import message as crud_message
from app.models.models import Message, MessageStatus, ChannelType
from app.schemas.message import MessageCreate
from app.services.consent import ConsentService
from app.services.rate_limit import RateLimitService
from app.utils.sms_provider import send_sms
from app.utils.email_provider import send_email

class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.consent_service = ConsentService(db)
        self.rate_limit_service = RateLimitService(db)

    def send_message(
        self,
        sender_phone: str,
        recipient_phone: Optional[str] = None,
        recipient_email: Optional[str] = None,
        text: str = "",
        channels: ChannelType = ChannelType.SMS,
        sender_user_id: Optional[int] = None,
        order_id: Optional[uuid.UUID] = None
    ) -> Message:
        # 1. Проверка лимитов для отправителя
        if not self.rate_limit_service.check_limit(sender_phone):
            raise ValueError("Превышен лимит отправок в час")

        # 2. Проверка согласия получателя
        if recipient_phone:
            consent = self.consent_service.get_consent(phone=recipient_phone)
            if consent and consent.status == "blocked":
                raise ValueError("Получатель запретил получение сообщений")
        if recipient_email:
            consent = self.consent_service.get_consent(email=recipient_email)
            if consent and consent.status == "blocked":
                raise ValueError("Получатель запретил получение сообщений")

        # 3. Создание записи сообщения
        if not order_id:
            order_id = uuid.uuid4()
        msg_in = MessageCreate(
            sender_phone=sender_phone,
            recipient_phone=recipient_phone,
            recipient_email=recipient_email,
            text=text,
            channels=channels,
            sender_user_id=sender_user_id,
            order_id=order_id
        )
        message = crud_message.create(self.db, obj_in=msg_in)

        # 4. Отправка через внешние провайдеры
        try:
            if channels in (ChannelType.SMS, ChannelType.BOTH) and recipient_phone:
                send_sms(recipient_phone, text)
            if channels in (ChannelType.EMAIL, ChannelType.BOTH) and recipient_email:
                send_email(recipient_email, "Сообщение от MSGPRO", text)
            # Обновляем статус на SENT
            message = crud_message.update(
                self.db,
                db_obj=message,
                obj_in={"status": MessageStatus.SENT}
            )
        except Exception as e:
            # Обновляем статус на FAILED
            message = crud_message.update(
                self.db,
                db_obj=message,
                obj_in={"status": MessageStatus.FAILED, "error_message": str(e)}
            )
            raise

        # 5. Увеличиваем счётчик лимита
        self.rate_limit_service.increment(sender_phone)

        return message

    def send_bulk(
        self,
        sender_phone: str,
        recipients: List[dict],
        text: str,
        channels: ChannelType = ChannelType.SMS,
        sender_user_id: Optional[int] = None
    ) -> List[Message]:
        """Массовая отправка: recipients = [{'phone': '...', 'email': '...'}, ...]"""
        order_id = uuid.uuid4()
        messages = []
        for recipient in recipients:
            msg = self.send_message(
                sender_phone=sender_phone,
                recipient_phone=recipient.get('phone'),
                recipient_email=recipient.get('email'),
                text=text,
                channels=channels,
                sender_user_id=sender_user_id,
                order_id=order_id
            )
            messages.append(msg)
        return messages

    def get_by_order_id(self, order_id: str) -> List[Message]:
        return crud_message.get_by_order_id(self.db, order_id=order_id)

    def get_sender_history(self, sender_phone: str, skip: int = 0, limit: int = 100) -> List[Message]:
        return crud_message.get_by_sender_phone(self.db, sender_phone=sender_phone, skip=skip, limit=limit)