# app/models/models.py

import enum
import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Index,
    Text,
    create_engine,
    text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session,joinedload
from sqlalchemy.sql import func

from app.config.config import settings

# --- Подключение к БД ---
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"options": "-c timezone=Europe/Moscow"}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Enums ---

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


class PermissionProhibitionType(str, enum.Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"


class PermissionProhibitionStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DELETED = "deleted"


class UserDocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DELETED = "deleted"


class VerificationType(str, enum.Enum):
    LOGIN = "login"
    PERMISSION = "permission"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class UserDocumentType(str, enum.Enum):
    TERMS = "terms"
    PRIVACY = "privacy"


class OrderStatus(str, enum.Enum):
    PROCESSING = "processing" #формирование заказа
    PENDING = "pending" #отправка заказа
    COMPLETED = "completed" #успешная отправка заказа
    FAILED = "failed" #отправка заказа с ошибками


class ApiResponseStatus(str, enum.Enum):
    OK = "ok"
    INFO = "info"
    ERROR = "error"
    WARNING = "warning"


# --- Миксины ---

class IdentifierMixin:
    id = Column(Integer, primary_key=True, index=True)


class CreatedMixin:
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class UpdatedMixin:
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class IsActiveMixin:
    is_active = Column(Boolean, default=True, nullable=False)


class CreateUpdateMixin(CreatedMixin, UpdatedMixin):
    pass


# --- Вспомогательные M2M таблицы ---

# Связь Заказа с физическими Контактами получателей
class OrderContactLink(Base, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "order_contacts"

    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="RESTRICT"), primary_key=True)


# Связь Карточки персоны (Person) с физическими Контактами (Contact)
class PersonContactLink(Base, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "person_contacts"

    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="RESTRICT"), primary_key=True)
    is_primary = Column(Boolean, default=False, nullable=False)  # Основной канал для данной персоны

    person = relationship("Person", back_populates="contact_links")
    contact = relationship("Contact", back_populates="person_links")


# Связь Карточки персоны (Person) с Группой (PersonGroup)
class PersonGroupLink(Base, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "person_group_links"

    group_id = Column(Integer, ForeignKey("person_groups.id", ondelete="CASCADE"), primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)

    group = relationship("PersonGroup", back_populates="person_links")
    person = relationship("Person", back_populates="group_links")


# --- Модели адресной книги, групп, каналов и контактов ---

# Группа персон (сегмент адресной книги конкретного клиента)
class PersonGroup(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "person_groups"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(250), nullable=True)

    user = relationship("User", back_populates="groups")
    person_links = relationship("PersonGroupLink", back_populates="group", cascade="all, delete-orphan")
    persons = relationship("Person", secondary="person_group_links", back_populates="groups", viewonly=True)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_group_name"),
        # Строка с Index("ix_person_groups_user_id", "user_id") удалена
    )

# Карточка адресата в адресной книге Клиента (User). Может состоять в группах или существовать отдельно
class Person(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "persons"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    description = Column(String(250), nullable=True)

    # Привязка к пользователю-владельцу
    user = relationship("User", back_populates="persons")

    # Группы, в которых состоит персона
    group_links = relationship("PersonGroupLink", back_populates="person", cascade="all, delete-orphan")
    groups = relationship("PersonGroup", secondary="person_group_links", back_populates="persons", viewonly=True)

    # Каналы связи персоны
    contact_links = relationship("PersonContactLink", back_populates="person", cascade="all, delete-orphan")
    contacts = relationship("Contact", secondary="person_contacts", back_populates="persons", viewonly=True)

    __table_args__ = (
        Index("ix_persons_user_full_name", "user_id", "full_name"),
    )


# Справочник каналов доставки сообщений (phone, email, telegram)
class S_Channel(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "s_channels"

    code = Column(String(20), unique=True, nullable=False)
    description = Column(String(100), nullable=True)

    identifiers = relationship("S_ChannelIdentifier", back_populates="channel", cascade="all, delete-orphan")


# Справочник типов идентификаторов контакта (phone, email)
class S_ChannelIdentifier(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "s_channel_identifiers"

    channel_id = Column(Integer, ForeignKey("s_channels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    description = Column(String(100), nullable=True)
    validation_regex = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)

    channel = relationship("S_Channel", back_populates="identifiers")
    messages = relationship("Message", back_populates="channel_identifier")
    contacts = relationship("Contact", back_populates="channel_identifier")

    __table_args__ = (
        UniqueConstraint("channel_id", "name", name="uq_channel_field"),
        Index(
            "uq_one_is_default_identifier_per_channel",
            "channel_id",
            unique=True,
            postgresql_where=text("is_default = true")
        ),
    )


# Справочник юридических документов (Terms, Privacy Policy)
class S_Document(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "s_documents"

    doc_type = Column(String(50), nullable=False)
    version = Column(String(20), nullable=False)
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    effective_date = Column(DateTime, server_default=func.now(), nullable=False)

    user_documents = relationship("UserDocument", back_populates="document")

    __table_args__ = (
        UniqueConstraint("doc_type", "version", name="uq_doc_version"),
        Index(
            "uq_active_document_per_type",
            "doc_type",
            unique=True,
            postgresql_where=text("is_active = true")
        ),
    )


# Клиент сервиса (отправитель рассылок)
class User(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "users"

    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)

    persons = relationship("Person", back_populates="user", cascade="all, delete-orphan")
    groups = relationship("PersonGroup", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="sender")
    orders = relationship("Order", back_populates="user")
    verification_codes = relationship("VerificationCode", back_populates="user")
    user_documents = relationship("UserDocument", back_populates="user")


# Глобальная точка доставки (физический номер телефона или email адрес)
class Contact(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "contacts"

    channel_identifier_id = Column(Integer, ForeignKey("s_channel_identifiers.id", ondelete="RESTRICT"), nullable=False)
    value = Column(String(255), nullable=False)

    persons = relationship("Person", secondary="person_contacts", back_populates="contacts", viewonly=True)
    person_links = relationship("PersonContactLink", back_populates="contact", cascade="all, delete-orphan")
    channel_identifier = relationship("S_ChannelIdentifier", back_populates="contacts")
    orders = relationship("Order", secondary="order_contacts", back_populates="contacts")
    permissions_prohibitions = relationship("PermissionProhibition", back_populates="contact", cascade="all, delete-orphan")
    verification_codes = relationship("VerificationCode", back_populates="contact", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("channel_identifier_id", "value", name="uq_channel_identifier_contact_value"),
        Index("ix_contacts_lookup", "channel_identifier_id", "value"),
    )


# --- Модели юридических документов и согласий ---

class UserDocument(Base, IdentifierMixin, CreatedMixin):
    __tablename__ = "user_documents"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("s_documents.id", ondelete="RESTRICT"), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    status = Column(Enum(UserDocumentStatus), default=UserDocumentStatus.DRAFT, nullable=False)
    verification_code_id = Column(Integer, ForeignKey("verification_codes.id", ondelete="SET NULL"), nullable=True)

    document = relationship("S_Document", back_populates="user_documents")
    user = relationship("User", back_populates="user_documents")
    verification_code = relationship("VerificationCode")

    __table_args__ = (
        Index("ix_user_doc_lookup", "document_id", "user_id"),
    )


# Глобальное правило согласия/запрета на физический контакт (независимо от адресных книг)
class PermissionProhibition(Base, IdentifierMixin, CreateUpdateMixin, IsActiveMixin):
    __tablename__ = "permissions_prohibitions"

    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    type = Column(Enum(PermissionProhibitionType), default=PermissionProhibitionType.ALLOWED, nullable=False)
    status = Column(Enum(PermissionProhibitionStatus), default=PermissionProhibitionStatus.DRAFT, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    verification_code_id = Column(Integer, ForeignKey("verification_codes.id", ondelete="SET NULL"), nullable=True)

    contact = relationship("Contact", back_populates="permissions_prohibitions")
    verification_code = relationship("VerificationCode")

    __table_args__ = (
        Index(
            "uq_active_permission_per_contact",
            "contact_id",
            unique=True,
            postgresql_where=text("is_active = true")
        ),
        Index("ix_permissions_prohibitions_lookup", "contact_id", "status"),
    )


# --- Заказы, сообщения и верификация ---

class Order(Base, IdentifierMixin, CreateUpdateMixin):
    __tablename__ = "orders"

    uuid = Column(PGUUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_identifier = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    user_agent = Column(String(255), nullable=True)
    text_preview = Column(String(1000), nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)
    is_flagged = Column(Boolean, default=False, nullable=False)
    flag_reason = Column(String(100), nullable=True)

    user = relationship("User", back_populates="orders")
    contacts = relationship("Contact", secondary="order_contacts", back_populates="orders")
    messages = relationship("Message", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_order_sender_antiabuse", "ip_address", "content_hash"),
    )


class Message(Base, IdentifierMixin, CreateUpdateMixin):
    __tablename__ = "messages"

    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_identifier = Column(String(255), nullable=True)
    channel_identifier_id = Column(Integer, ForeignKey("s_channel_identifiers.id", ondelete="RESTRICT"), nullable=False)
    recipient_value = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    repeat_counter=Column(Integer, default=0, nullable=False)
    sender = relationship("User", back_populates="messages")
    order = relationship("Order", back_populates="messages")
    channel_identifier = relationship("S_ChannelIdentifier", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_recipient_guard", "recipient_value", "created_at"),
        Index("ix_messages_status_processing", "status", "created_at"),
    )


class VerificationCode(Base, IdentifierMixin, CreatedMixin):
    __tablename__ = "verification_codes"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True)
    code = Column(String(6), nullable=False)
    type = Column(Enum(VerificationType), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)

    contact = relationship("Contact", back_populates="verification_codes")
    user = relationship("User", back_populates="verification_codes")

    __table_args__ = (
        Index("idx_vc_lookup", "contact_id", "code", "type", "used"),
    )


class Feedback(Base, IdentifierMixin, CreateUpdateMixin):
    __tablename__ = "feedbacks"

    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=False)
    topic = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    user_agent = Column(String(255), nullable=True)
    ip = Column(String(50), nullable=True)