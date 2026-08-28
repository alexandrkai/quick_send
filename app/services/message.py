from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from app.crud import order as crud_order, message as crud_message
from app.models.models import Order, OrderStatus,Message, MessageStatus
from app.schemas.order import OrderCreate
from app.schemas.message import MessageCreate
from app.services.consent import ConsentService
from app.services.rate_limit import RateLimitService

class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.consent_service = ConsentService(db)
        self.rate_limit_service = RateLimitService(db)

    def send_bulk(
        self,
        sender_phone: str,
        recipients: List[dict],
        text: str,
        channel_type: str,  # 'sms', 'email', 'both'
        sender_user_id: Optional[int] = None
    ) -> Order:
        # 1. Проверка лимитов
        if not self.rate_limit_service.check_limit(sender_phone):
            raise ValueError("Превышен лимит отправок в час")

        # 2. Создаём Order
        order_in = OrderCreate(
            user_id=sender_user_id,
            sender_phone=sender_phone,
            channel_type=channel_type,
            total_recipients=len(recipients),
            text_preview=text[:100]
        )
        order = crud_order.create(self.db, obj_in=order_in)

        # 3. Для каждого получателя создаём Message
        for recipient in recipients:
            # Проверка согласия
            consent = self.consent_service.get_consent_by_identifier(
                recipient.get('channel_type'),
                recipient.get('value')
            )
            if consent and consent.status == "blocked":
                # Можно пропустить или записать ошибку
                continue

            # Определяем канал
            # ... (логика определения channel_identifier_id)

            msg_in = MessageCreate(
                order_id=order.id,
                user_id=sender_user_id,
                channel_identifier_id=channel_identifier_id,
                recipient_value=recipient['value'],
                text=text
            )
            crud_message.create(self.db, obj_in=msg_in)

        # 4. Обновляем статус Order
        crud_order.update(self.db, db_obj=order, obj_in={"status": OrderStatus.COMPLETED})
        self.rate_limit_service.increment(sender_phone)
        return order