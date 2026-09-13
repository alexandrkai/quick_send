import hashlib
from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.models import (
    Contact,
    Message,
    MessageStatus,
    Order,
    OrderStatus,
    PermissionProhibition,
    PermissionProhibitionStatus,
    PermissionProhibitionType,
    S_Channel,
    S_ChannelIdentifier,
)
from app.schemas.schemas import MessageCreate, OrderCreate
from app.services.channel import ChannelService
from app.services.contact import ContactService
from app.services.rate_limit import RateLimitService

crud_order = CRUDBase[Order, OrderCreate, dict](Order)
crud_message = CRUDBase[Message, MessageCreate, dict](Message)


class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.rate_limit_service = RateLimitService(db)
        self.channel_service = ChannelService(db)
        self.contact_service = ContactService(db)

    def _get_default_identifier(self, channel_code: str) -> S_ChannelIdentifier:
        identifier = (
            self.db.query(S_ChannelIdentifier)
            .join(S_Channel, S_Channel.id == S_ChannelIdentifier.channel_id)
            .filter(
                S_Channel.code == channel_code,
                S_ChannelIdentifier.is_default.is_(True),
                S_ChannelIdentifier.is_active.is_(True),
            )
            .first()
        )
        if not identifier:
            raise ValueError(f"Дефолтный идентификатор для канала '{channel_code}' не настроен")
        return identifier

    def _is_contact_blocked(self, contact_id: int) -> bool:
        """Проверяет глобальный активный запрет на контакт."""
        rule = (
            self.db.query(PermissionProhibition)
            .filter(
                PermissionProhibition.contact_id == contact_id,
                PermissionProhibition.status == PermissionProhibitionStatus.ACTIVE,
                PermissionProhibition.type == PermissionProhibitionType.BLOCKED,
                PermissionProhibition.is_active.is_(True),
            )
            .first()
        )
        return rule is not None

    def send_bulk_email_phone(
        self,
        sender_phone: str,
        recipients: List[dict],
        text: str,
        default_channel_code: str,
        sender_user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> Order:
        # 1. Проверка лимитов отправки
        if not self.rate_limit_service.check_limit(sender_phone):
            raise ValueError("Превышен лимит отправок сообщений в час")

        # 2. Вычисление хеша контента для антиспама
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # 3. Создание заказа (содержит только актуальные поля модели Order)
        order_in = OrderCreate(
            user_id=sender_user_id,
            ip_address=ip_address,
            text_preview=text,
            content_hash=content_hash,
            status=OrderStatus.PROCESSING,
        )
        order = crud_order.create(self.db, obj_in=order_in)

        # 4. Формирование сообщений по получателям
        created_messages_count = 0
        for recipient in recipients:
            raw_value = str(recipient.get("value", "")).strip()
            ch_code = recipient.get("channel_type") or default_channel_code

            if not raw_value:
                continue

            identifier = self._get_default_identifier(ch_code)

            # Находим или регистрируем системный контакт
            contact = self.contact_service.get_or_create_contact(
                channel_identifier_id=identifier.id,
                value=raw_value,
            )

            # Проверяем глобальный запрет
            if self._is_contact_blocked(contact.id):
                # Фиксируем отмененное сообщение со статусом ошибки
                msg_in = MessageCreate(
                    order_id=order.id,
                    user_id=sender_user_id,
                    channel_identifier_id=identifier.id,
                    recipient_value=raw_value,
                    text=text,
                    status=MessageStatus.FAILED,
                    error_message="Получатель запретил рассылку на данный контакт",
                )
                crud_message.create(self.db, obj_in=msg_in)
                continue

            # Создаем сообщение готовое к отправке
            msg_in = MessageCreate(
                order_id=order.id,
                user_id=sender_user_id,
                channel_identifier_id=identifier.id,
                recipient_value=raw_value,
                text=text,
                status=MessageStatus.PENDING,
            )
            crud_message.create(self.db, obj_in=msg_in)
            created_messages_count += 1

        # 5. Завершение заказа и учет счетчиков
        crud_order.update(self.db, db_obj=order, obj_in={"status": OrderStatus.COMPLETED})
        self.rate_limit_service.increment(sender_phone)

        # Обновляем объект, чтобы подтянулись созданные связанные сообщения
        self.db.refresh(order)
        return order