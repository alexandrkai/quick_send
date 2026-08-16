# app/services/consent.py
from sqlalchemy.orm import Session
from datetime import datetime
from app.crud import consent as crud_consent
from app.models.models import Consent, ConsentStatus
from app.schemas.consent import ConsentCreate
from app.services.verification import VerificationService

class ConsentService:
    def __init__(self, db: Session):
        self.db = db
        self.verification_service = VerificationService(db)

    def get_consent(self, phone: str = None, email: str = None) -> Consent | None:
        if phone:
            return crud_consent.get_by_phone(self.db, phone=phone)
        elif email:
            return crud_consent.get_by_email(self.db, email=email)
        return None

    def set_consent(self, phone: str = None, email: str = None, status: ConsentStatus = ConsentStatus.ALLOWED) -> Consent:
        existing = self.get_consent(phone, email)
        if existing:
            return crud_consent.set_status(self.db, consent=existing, status=status)
        else:
            consent_in = ConsentCreate(phone=phone, email=email, status=status)
            return crud_consent.create(self.db, obj_in=consent_in)

    def request_consent_verification(self, phone: str = None, email: str = None) -> str:
        """Инициирует верификацию для подтверждения согласия (запрета/разрешения)."""
        # Генерируем код для подтверждения
        code = self.verification_service.generate_code(phone, email, type="consent")
        return code

    def confirm_consent(self, phone: str = None, email: str = None, code: str=None) -> bool:
        """Подтверждает согласие после верификации."""
        vc = self.verification_service.get_valid_code_obj(phone, email, code)
        if not vc:
            return False
        # Находим или создаём запись согласия
        consent = self.get_consent(phone, email)
        if not consent:
            # По умолчанию создаём разрешённое, но можно и заблокированное — зависит от бизнес-логики
            consent = self.set_consent(phone, email, ConsentStatus.ALLOWED)
        # Отмечаем подтверждение
        crud_consent.update(self.db, db_obj=consent, obj_in={
            "confirmed_at": datetime.utcnow(),
            "verification_code_id": vc.id
        })
        # Помечаем код как использованный
        self.verification_service.verify_code(phone, email, code)  # это установит used=True
        return True

    def block_consent(self, phone: str = None, email: str = None) -> bool:
        """Блокирует получение сообщений на указанный контакт (требует подтверждения)."""
        # Здесь можно либо сразу менять статус (если не нужна верификация), либо требовать подтверждение.
        # По вашему дизайну: для блокировки требуется подтверждение через код.
        # Поэтому мы не меняем статус напрямую, а инициируем процесс.
        # Но у вас может быть и мгновенная блокировка. Я предложу гибкий вариант:
        # если нужно подтверждение, вызываем request_consent_verification.
        # Либо можно сразу установить статус BLOCKED, но тогда потом подтверждать не надо.
        # Выберите вариант.
        consent = self.get_consent(phone, email)
        if consent:
            # Если хотим заблокировать без подтверждения (только владелец может, но он подтвердит через код)
            # Это упрощённо, но для полноты реализую с подтверждением:
            self.request_consent_verification(phone, email)
            return True
        return False