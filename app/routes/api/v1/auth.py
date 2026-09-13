# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status,Response
from sqlalchemy.orm import Session
from app.schemas.schemas import PhoneRequest,CodeRequest,PasswordLoginRequest,RegisterRequest,CheckApprovalResponse,CheckApprovalRequest
from app.utils.sms_provider import send_sms
from app.utils.email_provider import send_email
from app.models.models import get_db
from app.services.user import UserService, crud_user,User
from app.services.verification import VerificationService
from app.services.channel import ChannelService
from app.core.security import create_access_token, verify_password, get_password_hash,get_current_user_from_httponly_cookies,set_HTTPOnly_Cookie,delete_HTTPOnly_Cookie
from app.crud.document import crud_document
from app.crud.user_document import crud_user_document
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas import DocumentInfo
from app.models import (
    get_db,
    ApprovalType
)

router = APIRouter(prefix="/auth", tags=["Авторизация и верификация"])

@router.post("/request-sms")
def request_sms_code(data: PhoneRequest, db: Session = Depends(get_db)):
    """Запрос кода для входа по СМС."""
    try:
        verification_service=VerificationService(db)
        return verification_service.request_code_user(data)
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/verify-sms")
def verify_sms_code(data: CodeRequest, db: Session = Depends(get_db)):
    """Подтверждение СМС-кода и выдача JWT."""
    verification_service = VerificationService(db)
    channel_service =ChannelService(db)
    channel=channel_service.get_channel_by_code("phone")
    if not verification_service.verify_code(channel,data.phone, data.code,"login"):
        raise HTTPException(status_code=400, detail="Неверный или просроченный код")
    # Найти или создать пользователя
    user_service = UserService(db)
    user = user_service.find_and_create_user(data.phone)
    # if not user:
    #     user = user_service.create_user(phone=data.phone)
    # Создаём токен
    token = create_access_token({"sub": user.phone})
    # return {"access_token": token, "token_type": "bearer", "user_id": user.id}
    # response = JSONResponse({
    #     "status": "ok",
    #     "user_id": user.id,
    #     "message": "Верификация успешна"
    # })
    # response.set_cookie(
    #     key="access_token",
    #     value=token,
    #     httponly=True,
    #     secure=True,        # Только для HTTPS
    #     samesite="lax",     # Защита от CSRF
    #     max_age=60*60# пока сделал срок действия 1 час *24*7  # 7 дней (или используйте expires)
    # )
    # return response
    data={
        "status": "ok",
        "user_id": user.id,
        "message": "Верификация успешна"
    }
    response=set_HTTPOnly_Cookie(data,token)
    return response

@router.post("/login")
def login_password(data: PasswordLoginRequest, db: Session = Depends(get_db)):
    """Вход по паролю (если есть)."""
    user_service = UserService(db)
    user = user_service.get_user_by_phone(data.phone)
    if not user or not user.password_hash:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    token = create_access_token({"sub": user.phone})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/register")
def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    """Регистрация с паролем."""
    user_service = UserService(db)
    existing = user_service.get_user_by_phone(data.phone)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким телефоном уже существует")
    # Можно добавить проверку, что телефон подтверждён, но пока пропускаем
    user = user_service.create_user(
        phone=data.phone,
        email=data.email,
        full_name=data.full_name,
        password=data.password
    )
    token = create_access_token({"sub": user.phone})
    return {"access_token": token, "token_type": "bearer", "user_id": user.id}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user_from_httponly_cookies)):
    return current_user

# для токена из обычных кук
@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"status": "ok"}

# для токена HTTPOnly
@router.post("/logout_httponly")
def logout_HTTPOnly(response: Response):
    # Удаляем куку, устанавливая её с истекшим сроком
    # response.delete_cookie(
    #     key="access_token",
    #     path="/",
    #     secure=True,  # если используете HTTPS
    #     httponly=True,
    #     samesite="lax"
    # )
    delete_HTTPOnly_Cookie(response,name_cookie="access_token")
    return {"status": "ok", "message": "Logged out"}

@router.post(
    "/check-user-documents",
    response_model=CheckApprovalResponse,
    summary="Проверка наличия согласия на актуальные условия и политику",
)
def check_user_consent(
    payload: CheckApprovalRequest,
    db: Session = Depends(get_db),
):
    # 1. Получаем активные документы через crud
    docs = crud_document.get_active_terms_and_privacy(db)

    active_terms = next((d for d in docs if getattr(d, 'doc_type', None) in ('terms', ApprovalType.TERMS)), None)
    active_privacy = next((d for d in docs if getattr(d, 'doc_type', None) in ('privacy', ApprovalType.PRIVACY)), None)

    if not active_terms or not active_privacy:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Активные версии документов (Условия или Политика) не найдены в базе данных",
        )

    # 2. Ищем пользователя по номеру телефона
    user = crud_user.get_by_phone(db, phone=payload.phone)

    if not user:
        # Новый пользователь ещё не соглашался ни с чем
        need_consent = True
    else:
        # 3. Проверяем принятые документы пользователя по user_id со статусом APPROVED
        approved_doc_ids = set(
            crud_user_document.get_user_approved_document_ids(db, user_id=user.id)
        )
        has_terms = active_terms.id in approved_doc_ids
        has_privacy = active_privacy.id in approved_doc_ids
        need_consent = not (has_terms and has_privacy)

    if need_consent:
        return CheckApprovalResponse(
            need_consent=True,
            terms=DocumentInfo(
                id=active_terms.id,
                version=active_terms.version,
                title=active_terms.title,
                content=active_terms.content,
            ),
            privacy=DocumentInfo(
                id=active_privacy.id,
                version=active_privacy.version,
                title=active_privacy.title,
                content=active_privacy.content,
            ),
        )

    return CheckApprovalResponse(
        need_consent=False,
        terms=None,
        privacy=None,
    )