from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config.config import settings
from app.models.models import (
    UserDocumentStatus,
    UserDocumentType,
    ChannelType,
    ContactType,
    MessageStatus,
    OrderStatus,
    PermissionProhibitionType,
    UserRole,
    VerificationType,
    ApiResponseStatus,
)

EMAIL_REGEX = getattr(
    settings, "EMAIL_VALIDATION_REGEX", r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)


# --- Базовые типы контактов ---

class PhoneBase(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean_phone = re.sub(r"[\s\(\)\-]", "", v)
        if clean_phone.startswith("8") and len(clean_phone) == 11:
            clean_phone = "+7" + clean_phone[1:]
        if not re.match(settings.PHONE_VALIDATION_REGEX, clean_phone):
            raise ValueError(
                "Номер телефона должен быть в формате +7XXXXXXXXXX")
        return clean_phone


class EmailBase(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v:
            raise ValueError("Email не может быть пустым")
        clean_email = v.strip().lower()
        if not re.match(EMAIL_REGEX, clean_email):
            raise ValueError("Некорректный формат email адреса")
        if len(clean_email) > 100:
            raise ValueError("Email не должен превышать 100 символов")
        return clean_email


# --- Аутентификация и запросы пользователей ---

class PhoneRequest(PhoneBase):
    pass


class CodeRequest(PhoneBase):
    code: str


class PasswordLoginRequest(PhoneBase):
    password: str


class RegisterRequest(PhoneBase):
    password: str
    full_name: Optional[str] = None
    email: Optional[str] = None


# --- Управление пользователями (User) ---

class UserBase(PhoneBase):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = True


class UserCreate(UserBase):
    password_hash: Optional[str] = Field(default=None)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password_hash: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Быстрая отправка и рассылка ---

class QuickSendRequest(PhoneBase):
    code: str
    terms_accepted: bool
    text: str
    contacts: List[dict]
    token: Optional[str] = Field(default=None)
    data_token: Optional[str] = Field(default=None)


class BulkSendRequest(PhoneBase):
    text: str
    channels: List[str]
    contacts: List[dict]


class SendSingleRequest(BaseModel):
    recipient_phone: Optional[str] = Field(default=None)
    recipient_email: Optional[str] = Field(default=None)
    text: str
    channels: List[str]


# --- Документы и Согласия (Approval / Document) ---

class CheckApprovalRequest(PhoneBase):
    pass


class DocumentInfo(BaseModel):
    id: int
    version: str
    title: Optional[str] = Field(default=None)
    content: str


class CheckApprovalResponse(BaseModel):
    need_consent: bool
    terms: Optional[DocumentInfo] = None
    privacy: Optional[DocumentInfo] = None


class ApprovalBase(BaseModel):
    document_id: int
    identifier_value: Optional[str] = None
    user_id: Optional[int] = Field(default=None)
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    verification_code_id: Optional[int] = Field(default=None)
    status: UserDocumentStatus = Field(default=UserDocumentStatus.DRAFT)


class ApprovalCreate(ApprovalBase):
    pass


class ApprovalUpdate(BaseModel):
    user_id: Optional[int] = Field(default=None)
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    verification_code_id: Optional[int] = Field(default=None)
    status: Optional[UserDocumentStatus] = None


class ApprovalInDBBase(ApprovalBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserDocument(ApprovalInDBBase):
    pass


# Алиасы под новую модель документов
class UserDocumentBase(ApprovalBase):
    pass


class UserDocumentCreate(ApprovalCreate):
    pass


class UserDocumentUpdate(ApprovalUpdate):
    pass


class UserDocumentInDB(ApprovalInDBBase):
    pass


class DocumentBase(BaseModel):
    doc_type: UserDocumentType
    version: str
    title: Optional[str] = Field(default=None)
    content: str
    effective_date: Optional[datetime] = Field(default=None)
    is_active: bool = False


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    version: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    effective_date: Optional[datetime] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class DocumentInDB(DocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Системные ответы API ---

class ApiResponse(BaseModel):
    status: ApiResponseStatus
    message: Optional[str] = Field(default=None)
    detail: Optional[str] = Field(default=None)
    data: Optional[Any] = None


# --- Контакты (Contact) ---

class ContactBase(BaseModel):
    channel_identifier_id: int
    value: str
    is_active: bool = Field(default=False)


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    value: Optional[str] = Field(default=None)
    is_active: Optional[bool] = None


class ContactInDB(ContactBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactCheckResponse(BaseModel):
    allowed: bool
    channel: str
    value: str
    message: str


# --- Проверочные коды (VerificationCode) ---

class VerificationCodeBase(BaseModel):
    code: str
    type: VerificationType
    expires_at: datetime
    contact_id: Optional[int] = None
    user_id: Optional[int] = Field(default=None)
    used: bool = False


class VerificationCodeCreate(VerificationCodeBase):
    pass


class VerificationCodeUpdate(BaseModel):
    used: Optional[bool] = Field(default=None)


class VerificationCodeInDB(VerificationCodeBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Разрешения и Запреты (PermissionProhibition) ---

class PermissionProhibitionBase(BaseModel):
    channel_id: Optional[int] = None
    contact_id: Optional[int] = None
    value: Optional[str] = None
    status: Optional[PermissionProhibitionType] = None
    type: Optional[PermissionProhibitionType] = None
    is_active: bool = False


class PermissionProhibitionCreate(PermissionProhibitionBase):
    confirmed_at: Optional[datetime] = Field(default=None)
    verification_code_id: Optional[int] = Field(default=None)


class PermissionProhibitionUpdate(BaseModel):
    status: Optional[PermissionProhibitionType] = None
    type: Optional[PermissionProhibitionType] = None
    is_active: Optional[bool] = None
    confirmed_at: Optional[datetime] = Field(default=None)
    verification_code_id: Optional[int] = Field(default=None)


class PermissionProhibitionInDB(PermissionProhibitionBase):
    id: int
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionProhibitionResponse(BaseModel):
    permission_prohibition: PermissionProhibitionInDB


class PermissionProhibitionRequestSMSResponse(PermissionProhibitionResponse):
    is_new: bool
    verification_code: Optional[VerificationCodeInDB] = None
    message: Optional[str] = Field(default=None)


class PermissionProhibitionApiResponse(BaseModel):
    status: Optional[str] = "ok"
    token: Optional[str] = None
    message: Optional[str] = None
    status_code: int
    data_token: Optional[str] = None


class LoginApiResponse(PermissionProhibitionApiResponse):
    data: Optional[dict] = None


class PermissionProhibitionRequestSMS(BaseModel):
    token: Optional[str] = None
    channel_identifier: ContactType
    value: str
    type: PermissionProhibitionType
    data_token: Optional[str] = None

    @field_validator("value")
    @classmethod
    def validate_and_normalize_value(cls, v: str, info) -> str:
        v = v.strip()
        channel_identifier = info.data.get("channel_identifier")
        if channel_identifier == ContactType.PHONE:
            digits = re.sub(r"\D", "", v)
            if digits.startswith("8") and len(digits) == 11:
                digits = "7" + digits[1:]
            elif digits.startswith("7") and len(digits) == 11:
                pass
            else:
                raise ValueError(
                    "Номер телефона должен содержать 11 цифр и относиться к РФ (+7/8)")
            if not digits.startswith("7"):
                raise ValueError(
                    "Поддерживаются только мобильные номера РФ (+7...)")
            return f"+{digits}"
        elif channel_identifier == ContactType.EMAIL:
            email_lower = v.lower()
            if not re.match(EMAIL_REGEX, email_lower):
                raise ValueError("Некорректный формат email")
            return email_lower
        return v


class PermissionProhibitionConfirmSMS(PermissionProhibitionRequestSMS):
    code: str


# --- Каналы и Идентификаторы (Channel / ChannelIdentifier) ---

class ChannelIdentifierBase(BaseModel):
    channel_id: int
    name: str
    validation_regex: Optional[str] = Field(default=None)


class ChannelIdentifierCreate(ChannelIdentifierBase):
    is_default: bool = False


class ChannelIdentifierUpdate(BaseModel):
    name: Optional[str] = Field(default=None)
    validation_regex: Optional[str] = Field(default=None)
    is_default: Optional[bool] = None


class ChannelIdentifierInDB(ChannelIdentifierBase):
    id: int
    is_default: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChannelBase(BaseModel):
    code: str


class ChannelCreate(ChannelBase):
    description: Optional[str] = Field(default=None)


class ChannelUpdate(BaseModel):
    code: Optional[str] = Field(default=None)
    description: Optional[str] = None


class ChannelInDB(ChannelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Обратная связь (Feedback) ---

class FeedbackCreate(BaseModel):
    name: Optional[str] = Field(default=None)
    email: EmailStr
    topic: Optional[str] = Field(default=None)
    message: str
    user_agent: Optional[str] = Field(default=None)
    ip: Optional[str] = Field(default=None)


class FeedbackInDB(FeedbackCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Заказы и Сообщения (Order / Message) ---

class MessageBase(BaseModel):
    recipient_value: str
    text: str


class MessageCreate(MessageBase):
    user_id: Optional[int] = Field(default=None)
    channel_identifier_id: int
    order_id: int
    status: MessageStatus
    error_message: Optional[str] = None

class MessageUpdate(BaseModel):
    status: Optional[MessageStatus] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)


class MessageInDB(MessageBase):
    id: int
    order_id: int
    status: MessageStatus
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    user_id: int
    sender_identifier: str
    ip_address: str
    text_preview: str
    content_hash: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    is_flagged : Optional[bool] = False
    flag_reason : Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None


class OrderInDB(OrderCreate):
    id: int
    uuid: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
