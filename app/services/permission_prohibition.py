# app/services/consent.py
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import HTTPException, status
from app.crud.channel import crud_channel
from app.crud.channel_identifier import crud_channel_identifier
from app.crud.permission_prohibition import crud_permission_prohibition
from app.crud.verification_code import crud_verification_code
from app.services.channel import ChannelService
from app.crud.contact import crud_contact
from app.models import *
from app.services.verification import VerificationService
from app.services.channel_identifier import ChannelIdentifierService
from app.core.exceptions import ConsentException
from app.schemas import *
from app.services.contact import ContactService
from app.core.redis.redis import *
import random


class PermissionProhibitionService:
    def __init__(self, db: Session):
        self.db = db
        self.verification_service = VerificationService(db)
        self.contact_service = ContactService(db)
        self.channel_identifier_service = ChannelIdentifierService(db)
        self.channel_service = ChannelService(db)

    def get_permission_prohibition_by_is_default_channel_identifier_and_value(
        self,
        value: str,
        channel_identifier_name: str
    ) -> Optional[PermissionProhibition]:
        return (
            self.db.query(PermissionProhibition)
            .join(Contact, Contact.id == PermissionProhibition.contact_id)
            .join(S_ChannelIdentifier, S_ChannelIdentifier.id == Contact.channel_identifier_id)
            .filter(
                S_ChannelIdentifier.name == channel_identifier_name,
                S_ChannelIdentifier.is_default.is_(True),
                S_ChannelIdentifier.is_active.is_(True),
                Contact.value == value,
                PermissionProhibition.is_active.is_(True),
                PermissionProhibition.status==PermissionProhibitionStatus.ACTIVE
            )
            .order_by(PermissionProhibition.confirmed_at.desc())
            .first()
        )

    def create_or_update_agreement(self, channel_identifier_name: str, value: str, status: PermissionProhibitionType, verification_code_id: Optional[int] = None) -> PermissionProhibitionRequestSMSResponse:
        """Создаем или обновляем существующее соглашение"""
        # ищем в наличии согласия
        agreement = self.get_permission_prohibition_by_is_default_channel_identifier_and_value(
            value, channel_identifier_name=channel_identifier_name)
        if agreement:
            if agreement.status == status:
                if status == PermissionProhibitionType.ALLOWED:
                    raise Exception(
                        "Согласие на рассылку сообщений уже предоставлено!")
                else:
                    raise Exception(
                        "Запрет на рассылку сообщений уже предоставлено!")
            # обновляем
            agreement = crud_permission_prohibition.update(self.db, db_obj=agreement, obj_in={
                "status": status,
                "confirmed_at": datetime.now(),
                "verification_code_id": verification_code_id
            })
            return PermissionProhibitionRequestSMSResponse(agreement=agreement, is_new=False)
        else:
            consent_in = PermissionProhibitionCreate(
                channel_id=channel_identifier_name.id,
                value=value,
                status=status,
                confirmed_at=datetime.now(),
                verification_code_id=verification_code_id
            )
            agreement = crud_permission_prohibition.create(
                self.db, obj_in=consent_in)
        return PermissionProhibitionRequestSMSResponse(agreement=agreement, is_new=True)

    def request_code(self, schema: PermissionProhibitionRequestSMS) -> PermissionProhibitionApiResponse:
        key = "permission_prohibition"

        # Получаем канал и его системный идентификатор
        _, identifier = self.channel_service.get_channel_and_default_channel_identifier(
            schema.channel_identifier
        )
        contact = self.contact_service.get_or_create_contact(
            identifier.id, schema.value)

        # Рейтлимит: максимум 10 SMS в час на контакт
        channel_id_str = getattr(
            schema.channel_identifier, "value", str(schema.channel_identifier))
        if channel_id_str == "phone":
            count = crud_verification_code.count_recent_codes_for_contact(
                self.db, contact_id=contact.id,hours=settings.LIMIT_PERIOD_HOURS
            )
            if count >= settings.LIMIT_COUNT_SMS_FOR_LIMIT_PERIOD_HOURS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Превышен лимит запросов SMS (не более 10 в час). Попробуйте позже."
                )

        # Проверка текущего активного правила
        active_rule = crud_permission_prohibition.get_active_by_contact(
            self.db, contact=contact)
        if active_rule and active_rule.status == PermissionProhibitionStatus.ACTIVE:
            if active_rule.type == schema.type:
                rule_text = "разрешена" if schema.type == PermissionProhibitionType.ALLOWED else "запрещена"
                return PermissionProhibitionApiResponse(
                    message=f"Для данного контакта рассылка уже {rule_text}.",
                    status_code=2,
                    token=None
                )

        # Формируем полезную нагрузку для сессии Redis
        perm_type_str = getattr(schema.type, "value", str(schema.type))
        data_token = {
            "channel_identifier": channel_id_str,
            "value": schema.value,
            "type": perm_type_str,
            "contact_id": contact.id
        }

        # Проверка наличия еще действующего кода (до 5 минут)
        active_code = crud_verification_code.get_active_code(
            self.db, contact_id=contact.id, type=VerificationType.PERMISSION
        )
        if active_code:
            data_token["vc_id"] = active_code.id
            seconds_left = max(
                0, int((active_code.expires_at - datetime.now()).total_seconds()))
            data = write_value(key, data_token, expires_in=seconds_left or 300)
            return PermissionProhibitionApiResponse(
                message=f"Код подтверждения ранее был отправлен. Повтор возможен через {seconds_left} сек.",
                status_code=1,
                token=data["verification_token"]
            )

        # Генерация и фиксация нового 6-значного кода
        # generated_code = "".join(random.choices("0123456789", k=6))
        # expires_at = datetime.now() + timedelta(seconds=settings.PERIOD_VALIDATED_SMS_CODE_SECONDS)
        # new_vc = crud_verification_code.create(
        #     self.db,
        #     obj_in={
        #         "contact_id": contact.id,
        #         "code": generated_code,
        #         "type": VerificationType.PERMISSION,
        #         "expires_at": expires_at,
        #         "used": False,
        #     },
        # )
        new_vc=self.verification_service.generate_code(contact=contact,type=VerificationType.PERMISSION)

        # Фиксация черновика согласия / запрета
        draft_pp = crud_permission_prohibition.upsert_draft(
            self.db,
            contact=contact,
            perm_type=schema.type,
            code_id=new_vc.id,
        )

        data_token.update({
            "vc_id": new_vc.id,
            "permission_prohibition_id": draft_pp.id
        })

        # Отправка через провайдер (SMS / Email)
        print(
            f"[GATEWAY MOCK] Отправка кода {new_vc.code} на {contact.value}")

        data = write_value(key, data_token, expires_in=300)
        return PermissionProhibitionApiResponse(
            message=f"Код подтверждения успешно отправлен. Срок действия — 5 минут.",
            status_code=1,
            token=data["verification_token"]
        )

    def confirm_code(self, schema: PermissionProhibitionConfirmSMS) -> PermissionProhibitionApiResponse:
        key = "permission_prohibition"

        if not schema.token or not check_exists(key, schema.token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "-5",
                    "message": "Срок действия кода истек или сессия не найдена. Запросите код заново."
                }
            )

        # Читаем данные сессии из Redis
        session_data = read_value(key, schema.token)

        # Валидируем соответствие контакта переданному токену
        req_channel = getattr(schema.channel_identifier,
                              "value", str(schema.channel_identifier))
        if session_data.get("channel_identifier") != req_channel or session_data.get("value") != schema.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "-4",
                    "message": "Данные формы не совпадают с запрошенной сессией подтверждения. Запросите код заново."
                }
            )

        # channel, identifier = self.channel_service.get_channel_and_default_channel_identifier(
        #     schema.channel_identifier
        # )
        # contact = self.contact_service.get_or_create_contact(identifier, schema.value)
        # if not contact:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Контакт с указанными реквизитами не найден"
        #     )
        contact_id = session_data.get("contact_id")
        active_code = crud_verification_code.get_active_code(
            self.db, contact_id=contact_id, type=VerificationType.PERMISSION
        )
        if not active_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "-3",
                    "message": "Срок действия проверочного кода истек. Запросите код заново."
                }
            )

        if active_code.code != schema.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "-2",
                    "message": "Неверный проверочный код. Проверьте правильность ввода."
                }
            )

        # Находим черновик перед началом транзакции
        draft = crud_permission_prohibition.get_draft_by_contact_id(
            self.db, contact_id=contact_id
        )
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "-1",
                    "message": "Настройки рассылки не сделаны. Повторите процедуру запроса кода."

                }
            )

        # Транзакция: гасим код -> деактивируем старое правило -> активируем драфт
        try:
            with self.db.begin_nested():
                # 1. Погасить проверочный код
                active_code.used = True
                self.db.add(active_code)

                # 2. Деактивировать все текущие активные правила контакта (чтобы не нарушить Unique Constraint)
                active_rules = (
                    self.db.query(PermissionProhibition)
                    .filter(
                        PermissionProhibition.contact_id == contact_id,
                        PermissionProhibition.is_active.is_(True),
                        PermissionProhibition.id != draft.id
                    )
                    .with_for_update()
                    .all()
                )
                for rule in active_rules:
                    rule.is_active = False
                    self.db.add(rule)

                # Применяем промежуточные изменения перед активацией нового правила
                self.db.flush()

                # 3. Активировать черновик
                crud_permission_prohibition.activate_permission(
                    self.db, record=draft, isCommit=False)

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка применения изменений в БД: {str(e)}"
            )

        # Удаляем ключ из Redis только после успешного коммита транзакции
        delete_value(key, schema.token)

        action_word = "разрешена" if draft.type == PermissionProhibitionType.ALLOWED else "запрещена"
        return PermissionProhibitionApiResponse(
            status_code=0,
            message=f"Рассылка на данный контакт {action_word}!",
            token=None
        )
