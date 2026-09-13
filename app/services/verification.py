import random
import string
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.config.config import settings
from app.crud.verification_code import crud_verification_code
from app.services.user import UserService
from app.services.channel import ChannelService
from app.services.channel_identifier import ChannelIdentifierService
from app.models.models import VerificationCode, User, Contact, VerificationType
from app.schemas.schemas import VerificationCodeCreate, PhoneRequest,LoginApiResponse
from app.core.redis import read_value,write_value

class VerificationService:
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db=db)
        self.channel_service = ChannelService(db)
        self.channel_identifier_service = ChannelIdentifierService(db)

    def generate_code(
        self,
        *,
        type: VerificationType,
        contact: Optional[Contact] = None,
        user: Optional[User] = None
    ) -> VerificationCode:
        if not contact and not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для генерации кода необходим контакт или пользователь"
            )

        if contact:
            channel_identifier = self.channel_identifier_service.get_by_id(contact.channel_identifier_id)
            if type == VerificationType.LOGIN and channel_identifier and channel_identifier.name == "email":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Регистрация и вход возможны только по телефону"
                )

        generated_code = "".join(random.choices(string.digits, k=6))
        expires_at = datetime.now() + timedelta(seconds=settings.PERIOD_VALIDATED_SMS_CODE_SECONDS)

        vc_in = VerificationCodeCreate(
            code=generated_code,
            type=type,
            expires_at=expires_at,
            used=False
        )

        if contact:
            vc_in.contact_id = contact.id
        if user:
            vc_in.user_id = user.id

        return crud_verification_code.create(self.db, obj_in=vc_in)

    def verify_code(
        self,
        code: str,
        type: VerificationType,
        *,
        contact: Optional[Contact] = None,
        user: Optional[User] = None
    ) -> Optional[VerificationCode]:
        vc = crud_verification_code.get_valid_code(
            self.db, contact=contact, user=user, code=code, type=type
        )
        if not vc:
            return None
        crud_verification_code.mark_used(self.db, code_obj=vc)
        return vc

    def get_and_generate_code_for_phone(
        self, phone: str, type: VerificationType, user: Optional[User] = None
    ) -> dict:
        if not user:
            user = self.user_service.find_and_create_user(phone=phone)

        vc = crud_verification_code.get_active_code(self.db, user_id=user.id, type=type)
        if not vc:
            vc = self.generate_code(type=type, user=user)
            return {"is_new": True, "vc": vc, "status": "ok"}

        return {"is_new": False, "vc": vc, "status": "ok"}

    def filter_active_code(
        self,
        *,
        type: VerificationType,
        user: Optional[User] = None,
        contact: Optional[Contact] = None
    ) -> Optional[VerificationCode]:
        contact_id = contact.id if contact else None
        user_id = user.id if user else None
        return crud_verification_code.get_active_code(
            self.db, contact_id=contact_id, user_id=user_id, type=type
        )
        
    def request_code_user(self,data: PhoneRequest):
        from app.crud.verification_code import crud_verification_code
        key = "permission_prohibition"

        # Получаем канал и его системный идентификатор
        user=self.user_service.find_and_create_user(data.phone)
        
        # Рейтлимит: максимум 10 SMS в час на контакт
        count = crud_verification_code.count_recent_codes_for_contact(
                self.db, user_id=user.id
            )
        if count >= settings.LIMIT_COUNT_SMS_FOR_LIMIT_PERIOD_HOURS:
            raise Exception("Превышен лимит запросов SMS (не более 10 в час). Попробуйте позже."                )

        # Проверка текущего активного правила
        # active_rule = crud_permission_prohibition.get_active_by_contact(
        #     self.db, contact=contact)
        # if active_rule and active_rule.status == PermissionProhibitionStatus.ACTIVE:
        #     if active_rule.type == schema.type:
        #         rule_text = "разрешена" if schema.type == PermissionProhibitionType.ALLOWED else "запрещена"
        #         return PermissionProhibitionApiResponse(
        #             message=f"Для данного контакта рассылка уже {rule_text}.",
        #             status_code=2,
        #             token=None
        #         )

        # # Формируем полезную нагрузку для сессии Redis
        # perm_type_str = getattr(schema.type, "value", str(schema.type))
        data_token = {
            "phone": data.phone,
            "user_id": user.id
        }

        # Проверка наличия еще действующего кода (до 5 минут)
        active_code = crud_verification_code.get_active_code(
            self.db, user_id=user.id, type=VerificationType.LOGIN
        )
        if active_code:
            data_token["vc_id"] = active_code.id
            seconds_left = max(
                0, int((active_code.expires_at - datetime.now()).total_seconds()))
            data = write_value(key, data_token, expires_in=seconds_left or 300)
            return LoginApiResponse(
                message=f"Код подтверждения ранее был отправлен. Повтор возможен через {seconds_left} сек.",
                status_code=1,
                token=data["verification_token"]
            )

        new_vc=self.generate_code(user=user,type=VerificationType.LOGIN)

        data_token.update({
            "vc_id": new_vc.id
        })

        # Отправка через провайдер (SMS / Email)
        print(
            f"[GATEWAY MOCK] Отправка кода {new_vc.code} на {user.phone}")

        data = write_value(key, data_token, expires_in=300)
        return LoginApiResponse(
            message=f"Код подтверждения успешно отправлен. Срок действия — 5 минут.",
            status_code=1,
            token=data["verification_token"]
        )
