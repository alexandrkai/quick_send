from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from app.crud import message as crud_message, user_contact as crud_user_contact, consent as crud_consent
from app.models.models import MessageStatus, ChannelType, ConsentStatus, Message
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

    def _check_consent(self, recipient_value: str, channel_type: ChannelType) -> bool:
        """Проверяет, разрешена ли отправка на этот контакт."""
        status = self.consent_service.get_consent_status(recipient_value, channel_type)
        return status == ConsentStatus.ALLOWED

    def send_message(
        self,
        user_id: int,
        recipient_value: str,
        channel_type: ChannelType,
        text: str,
        order_id: Optional[uuid.UUID] = None
    ) -> Message:
        # Проверка лимитов для отправителя
        if not self.rate_limit_service.check_limit(user_id):
            raise ValueError("Превышен лимит отправок в час")
        # Проверка согласия получателя
        if not self._check_consent(recipient_value, channel_type):
            raise ValueError("Получатель запретил получение сообщений")
        # Создаём запись
        if not order_id:
            order_id = uuid.uuid4()
        msg_in = MessageCreate(
            user_id=user_id,
            channel_identifier_id=self._get_channel_identifier_id(channel_type),
            recipient_value=recipient_value,
            text=text,
            order_id=order_id,
            status=MessageStatus.PENDING
        )
        message = crud_message.create(self.db, obj_in=msg_in)
        # Отправка через провайдер
        try:
            if channel_type == ChannelType.PHONE:
                send_sms(recipient_value, text)
            elif channel_type == ChannelType.EMAIL:
                send_email(recipient_value, "Сообщение от MSGPRO", text)
            message = crud_message.update(
                self.db,
                db_obj=message,
                obj_in={"status": MessageStatus.SENT}
            )
        except Exception as e:
            message = crud_message.update(
                self.db,
                db_obj=message,
                obj_in={"status": MessageStatus.FAILED, "error_message": str(e)}
            )
            raise
        # Увеличиваем счётчик лимита
        self.rate_limit_service.increment(user_id)
        return message

    def send_bulk(
        self,
        user_id: int,
        recipients: List[dict],
        text: str,
        channel_type: ChannelType
    ) -> List[Message]:
        order_id = uuid.uuid4()
        messages = []
        for recipient in recipients:
            value = recipient.get('phone') if channel_type == ChannelType.PHONE else recipient.get('email')
            if value:
                msg = self.send_message(
                    user_id=user_id,
                    recipient_value=value,
                    channel_type=channel_type,
                    text=text,
                    order_id=order_id
                )
                messages.append(msg)
        return messages