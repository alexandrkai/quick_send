# app/models.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, Index, Text, UUID, JSON
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import enum
import uuid
from sqlalchemy.sql import func

Base = declarative_base()

Channels = [
    {"name": "phone",
     "type_contacts": [
         {"name": "number_phone",
          "regex": r"^\+7\(?\d{3}\)?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}$"}
     ]},
    {"name": "email",
     "type_contacts": [
         {"name": "address_email",
          "regex": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"}
     ]}
    # ,{"name": "telegram",
    #  "type_contacts": [
    #      {"name": "username",
    #       "regex": r"^@?[a-zA-Z0-9_]{5,32}$"},
    #      {"name": "user_id",
    #       "regex": r"^\d+$"}
    #      ]}
]
# --- Enum ---


class ChannelType(str, enum.Enum):
    PHONE = "phone"
    EMAIL = "email"


class ContaactType(str, enum.Enum):
    PHONE = "phone"
    EMAIL = "email"


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class ConsentStatus(str, enum.Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"


class VerificationType(str, enum.Enum):
    LOGIN = "login"
    CONSENT = "consent"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class IdentifierMixin():
    id = Column(Integer, primary_key=True, index=True)


class CreatedMixin:
    created_at = Column(DateTime, server_default=func.now())


class UpdatedMixin:
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now())

# Класс для создания и обновления объектов
class CreateUpdate(CreatedMixin, UpdatedMixin):
    pass

# --- Models ---
# 2. Справочник каналов (ваш верхний уровень ChannelType)
class Channel(Base, IdentifierMixin, CreateUpdate):
    __tablename__ = "channels"

    code = Column(String(20), unique=True, nullable=False)  # 'phone', 'email'
    # Связи
    field_specs = relationship(
        "ChannelIdentifier", back_populates="channel", cascade="all, delete-orphan")
    user_contacts = relationship("UserContact", back_populates="channel")

# 3. Справочник полей контакта (ваш вложенный type_contacts + regex)
class ChannelIdentifier(Base, IdentifierMixin, CreateUpdate):
    __tablename__ = "channel_identifiers"

    channel_id = Column(Integer, ForeignKey(
        "channels.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(50), nullable=False)      # 'phone', 'email'
    # Ваша регулярка (опционально)
    validation_regex = Column(Text, nullable=True)

    # Уникальность: у одного канала не может быть двух полей с одинаковым именем
    __table_args__ = (
        UniqueConstraint('channel_id', 'field_name', name='uq_channel_field'),
    )

    # Связи
    channel = relationship("Channel", back_populates="field_specs")
    # Пока не связываем с контактами (можно добавить позже, если понадобится)


class User(Base, CreateUpdate, IdentifierMixin):
    __tablename__ = "users"

    # phone = Column(String(20), unique=True, nullable=False, index=True)
    # email = Column(String(100), unique=True, nullable=True, index=True)
    # вместо phone и email{"phone":"+79175729812","email":"kai@mail.ru"}
    contacts = Column(JSON, nullable=False, default=dict)
    full_name = Column(String(100), nullable=True)
    # для будущей регистрации
    password_hash = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # подтверждён ли телефон

    # relationships
    messages = relationship("Message", back_populates="sender")
    consents = relationship("Consent", back_populates="user")
    verification_codes = relationship(
        "VerificationCode", back_populates="user")
    contacts = relationship(
        "UserContact", back_populates="user", cascade="all, delete-orphan")

# 4. ГЛАВНАЯ таблица — контакты пользователей (ваши фактические данные)


class UserContact(Base, IdentifierMixin, CreatedMixin):
    __tablename__ = "user_contacts"
    # прежде чем создать согласие должен существовать контакт
    channel_identifier_id = Column(Integer, ForeignKey(
        "channel_identifiers.id", ondelete="CASCADE"), nullable=False)
    channel_identifier_value = Column(
        String(20), unique=True, nullable=False, index=True)
    # Уникальность: один пользователь — один канал (например, не может быть 2 телефона в одной записи)
    __table_args__ = (
        UniqueConstraint('user_id', 'channel_identifier_id', 'channel_id',
                         name='uq_channel_identifier_id_channel_identifier_value'),
        # Индекс для быстрого поиска контакта
        Index('ix_channel_identifier_value', 'channel_identifier_value'),
    )

    # Связи
    user = relationship("User", back_populates="contacts")
    channel_identifier = relationship(
        "ChannelIdentifier", back_populates="user_contacts")


class Consent(Base, CreateUpdate, IdentifierMixin):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint('channel_identifier_id', name='uq_consent_phone'),
        UniqueConstraint('email', name='uq_consent_email'),
    )
    # прежде чем сохранить информацию о Consent должен существовать UserContact
    user_contact_id = Column(Integer, ForeignKey(
        "user_contacts.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(ConsentStatus), default=ConsentStatus.ALLOWED)
    # когда подтверждено владельцем
    confirmed_at = Column(DateTime, nullable=True)
    verification_code_id = Column(Integer, ForeignKey(
        "verification_codes.id"), nullable=True)
    # relationships
    verification_code = relationship("VerificationCode")


class Message(Base, CreateUpdate, IdentifierMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index('idx_message_sender_phone', 'sender_phone'),
        Index('idx_message_recipient_phone', 'recipient_phone'),
        Index('idx_message_recipient_email', 'recipient_email'),
        Index('idx_message_order_id', 'order_id'),
        Index('idx_message_created_at', 'created_at'),
    )
    # прежде чем отправить сообщения, нужно создать User пусть даже сам пользователь не зарегистрирован и он не знает об этом. учитывая, что сообщения не будут отправлены пока он не пройдет верификацию через код в смс.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_identifier_id = Column(Integer, ForeignKey(
        "channel_identifiers.id", ondelete="CASCADE"), nullable=False)
    channel_identifier_value = Column(
        String(20), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=False)
    channels = Column(Enum(ChannelType), nullable=False)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    order_id = Column(PGUUID(as_uuid=True), default=uuid.uuid4,
                      nullable=False)  # группировка массовой отправки
    # ID от внешних провайдеров (JSON)
    error_message = Column(Text, nullable=True)
    delivered_at = Column(DateTime, nullable=True)  # когда доставлено

    # relationships
    sender = relationship("User", back_populates="messages")


class VerificationCode(Base, CreatedMixin, IdentifierMixin):
    __tablename__ = "verification_codes"
    __table_args__ = (
        Index('idx_vc_phone_code', 'phone', 'code'),
        Index('idx_vc_email_code', 'email', 'code'),
    )
    # прежде чем отправится код на почту или смс, должен быть создан контакт
    # пользователь сервиса прежде чем отправить сообщения, должен верифицироваться с помощью смс
    # пользователь прежде чем дать Consent(запрет или согласие) должен верифицироваться с помощью смс или с помощью почты
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # контакт для верификации.если телефон, то код будет отправлен на этот номер, если почта - письмо
    user_contact_id = Column(Integer, ForeignKey(
        "user_contacts.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(6), nullable=False)
    type = Column(Enum(VerificationType), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

    # relationships
    user = relationship("User", back_populates="verification_codes")
