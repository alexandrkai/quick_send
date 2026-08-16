# app/models.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, Index, Text, UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import enum
import uuid

Base = declarative_base()

# --- Enum ---
class ChannelType(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    BOTH = "both"

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


# --- Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)  # для будущей регистрации
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # подтверждён ли телефон
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    messages = relationship("Message", back_populates="sender")
    consents = relationship("Consent", back_populates="user")
    verification_codes = relationship("VerificationCode", back_populates="user")


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint('phone', name='uq_consent_phone'),
        UniqueConstraint('email', name='uq_consent_email'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # может быть анонимным
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(100), nullable=True, index=True)
    status = Column(Enum(ConsentStatus), default=ConsentStatus.ALLOWED)
    confirmed_at = Column(DateTime, nullable=True)  # когда подтверждено владельцем
    verification_code_id = Column(Integer, ForeignKey("verification_codes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    user = relationship("User", back_populates="consents")
    verification_code = relationship("VerificationCode")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index('idx_message_sender_phone', 'sender_phone'),
        Index('idx_message_recipient_phone', 'recipient_phone'),
        Index('idx_message_recipient_email', 'recipient_email'),
        Index('idx_message_order_id', 'order_id'),
        Index('idx_message_created_at', 'created_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # может быть анонимным
    sender_phone = Column(String(20), nullable=False)  # дублируем для истории
    recipient_phone = Column(String(20), nullable=True)
    recipient_email = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    channels = Column(Enum(ChannelType), nullable=False)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    order_id = Column(PGUUID(as_uuid=True), default=uuid.uuid4, nullable=False)  # группировка массовой отправки
    external_ids = Column(String(255), nullable=True)  # ID от внешних провайдеров (JSON)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)  # когда доставлено

    # relationships
    sender = relationship("User", back_populates="messages")


class VerificationCode(Base):
    __tablename__ = "verification_codes"
    __table_args__ = (
        Index('idx_vc_phone_code', 'phone', 'code'),
        Index('idx_vc_email_code', 'email', 'code'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # если привязан к пользователю
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    code = Column(String(6), nullable=False)
    type = Column(Enum(VerificationType), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relationships
    user = relationship("User", back_populates="verification_codes")