# app/models.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, Index, Text, JSON, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import enum
import uuid
from sqlalchemy.sql import func
from app.core.config import settings

# --- Подключение к БД ---
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    # Telegram пока исключён
]

# --- Enum ---

class ChannelType(str, enum.Enum):
    PHONE = "phone"
    EMAIL = "email"

class ContactType(str, enum.Enum):
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


# --- Миксины ---

class IdentifierMixin:
    id = Column(Integer, primary_key=True, index=True)

class CreatedMixin:
    created_at = Column(DateTime, server_default=func.now())

class UpdatedMixin:
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class CreateUpdate(CreatedMixin, UpdatedMixin):
    pass


# --- Модели ---

class Channel(Base, IdentifierMixin, CreateUpdate):
    __tablename__ = "channels"

    code = Column(String(20), unique=True, nullable=False)  # 'phone', 'email'
    field_specs = relationship(
        "ChannelIdentifier", back_populates="channel", cascade="all, delete-orphan")
    consents = relationship("Consent", back_populates="channel")  # связь с согласиями
    verification_codes = relationship("VerificationCode", back_populates="channel")  # связь с кодами


class ChannelIdentifier(Base, IdentifierMixin, CreateUpdate):
    __tablename__ = "channel_identifiers"

    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(50), nullable=False)      # 'number_phone', 'address_email'
    validation_regex = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('channel_id', 'field_name', name='uq_channel_field'),
    )

    channel = relationship("Channel", back_populates="field_specs")
    user_contacts = relationship("UserContact", back_populates="channel_identifier")


class User(Base, CreateUpdate, IdentifierMixin):
    __tablename__ = "users"

    contact_data = Column(JSON, nullable=False, default=dict)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    messages = relationship("Message", back_populates="sender")
    verification_codes = relationship("VerificationCode", back_populates="user")
    contacts = relationship(
        "UserContact", back_populates="user", cascade="all, delete-orphan")


class UserContact(Base, IdentifierMixin, CreatedMixin):
    __tablename__ = "user_contacts"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_identifier_id = Column(Integer, ForeignKey("channel_identifiers.id", ondelete="CASCADE"), nullable=False)
    channel_identifier_value = Column(String(255), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint('user_id', 'channel_identifier_id', name='uq_user_channel_identifier'),
        Index('ix_channel_identifier_value', 'channel_identifier_value'),
        Index('ix_user_contacts_user_id', 'user_id'),
    )

    user = relationship("User", back_populates="contacts")
    channel_identifier = relationship("ChannelIdentifier", back_populates="user_contacts")


class Consent(Base, IdentifierMixin, CreateUpdate):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint('channel_id', 'value', name='uq_consent_channel_value'),
        Index('ix_consent_value', 'value'),
    )

    # Ссылка на канал (phone или email) – внешний ключ на Channel.id
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    # Само значение (номер телефона или email)
    value = Column(String(255), nullable=False, index=True)
    status = Column(Enum(ConsentStatus), default=ConsentStatus.ALLOWED)
    confirmed_at = Column(DateTime, nullable=True)
    verification_code_id = Column(Integer, ForeignKey("verification_codes.id"), nullable=True)

    # Связи
    channel = relationship("Channel", back_populates="consents")
    verification_code = relationship("VerificationCode")


class Message(Base, CreateUpdate, IdentifierMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index('idx_message_order_id', 'order_id'),
        Index('idx_message_created_at', 'created_at'),
        Index('idx_message_recipient_value', 'recipient_value'),
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_identifier_id = Column(Integer, ForeignKey("channel_identifiers.id", ondelete="CASCADE"), nullable=False)
    recipient_value = Column(String(255), nullable=False, index=True)
    text = Column(Text, nullable=False)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    order_id = Column(PGUUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    error_message = Column(Text, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    sender = relationship("User", back_populates="messages")
    channel_identifier = relationship("ChannelIdentifier")


class VerificationCode(Base, CreatedMixin, IdentifierMixin):
    __tablename__ = "verification_codes"
    __table_args__ = (
        Index('idx_vc_value_code', 'value', 'code'),
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Ссылка на канал (phone или email) – внешний ключ на Channel.id
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    value = Column(String(255), nullable=False)  # телефон или email
    code = Column(String(6), nullable=False)
    type = Column(Enum(VerificationType), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

    user = relationship("User", back_populates="verification_codes")
    channel = relationship("Channel", back_populates="verification_codes")