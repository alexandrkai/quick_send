# app/services/verification.py
import random
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.crud import verification_code as crud_vc
from app.models.models import VerificationCode, VerificationType
from app.schemas.verification_code import VerificationCodeCreate
from app.utils.sms_provider import send_sms
from app.utils.email_provider import send_email

class VerificationService:
    def __init__(self, db: Session):
        self.db = db

    def generate_code(self, phone: str = None, email: str = None, type: VerificationType = VerificationType.LOGIN) -> str:
        # Генерация 6-значного кода
        code = ''.join(random.choices(string.digits, k=6))
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        vc_in = VerificationCodeCreate(
            phone=phone,
            email=email,
            code=code,
            type=type,
            expires_at=expires_at
        )
        vc = crud_vc.create(self.db, obj_in=vc_in)
        # Отправка кода
        if phone:
            send_sms(phone, f"Ваш код: {code}")
        elif email:
            send_email(email, "Код подтверждения", f"Ваш код: {code}")
        return code

    def verify_code(self, phone: str = None, email: str = None, code: str=None) -> bool:
        vc = crud_vc.get_valid_code(self.db, phone=phone, email=email, code=code)
        if not vc:
            return False
        crud_vc.mark_used(self.db, code_obj=vc)
        return True

    def get_valid_code_obj(self, phone: str = None, email: str = None, code: str=None) -> VerificationCode | None:
        return crud_vc.get_valid_code(self.db, phone=phone, email=email, code=code)