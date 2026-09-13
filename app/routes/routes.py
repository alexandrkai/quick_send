from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.models import get_db, ChannelType, PermissionProhibitionType, ContactType,PermissionProhibitionStatus
from app.services.permission_prohibition import PermissionProhibitionService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Список существующих статических файлов
VALID_PAGES = {
    "terms.html", "privacy.html"
}

# Карта коротких редиректов
REDIRECT_MAP = {
    "quick-send": "quick_send.html",
    "about": "about.html",
    "contact": "contact.html",
    "terms": "terms.html",
    "privacy": "privacy.html",
    # "login": "login.html",
    # "register": "signup.html",
    "permission_prohibition": f"permission_prohibition.html?action={PermissionProhibitionType.BLOCKED.value}",
}

# --- ПОДВИЖНЫЕ И КОНКРЕТНЫЕ РОУТЫ (FastAPI проверяет их первыми) ---


@router.get("/", response_class=HTMLResponse)
@router.get("/index.html", response_class=HTMLResponse)
async def index_page(request: Request):

    # Передаём Enum-объекты в контекст
    return templates.TemplateResponse(
        request,
        name="index.html",
        context={
            "page_title": "MSGPRO - Бесплатная отправка СМС и email",
            "ConsentStatus": PermissionProhibitionType,  # передаём весь Enum
            "ChannelType": ChannelType
        }
    )


@router.get("/about.html", response_class=HTMLResponse)
async def about_page(request: Request):

    # Передаём Enum-объекты в контекст
    return templates.TemplateResponse(
        request,
        name="about.html",
        context={
            "page_title": "MSGPRO - О нас",
            "ConsentStatus": PermissionProhibitionType,
            "ChannelType": ChannelType
        }
    )


@router.get("/contact.html", response_class=HTMLResponse)
async def about_page(request: Request):

    # Передаём Enum-объекты в контекст
    return templates.TemplateResponse(
        request,
        name="contact.html",
        context={
            "page_title": "MSGPRO - О нас",
            "ConsentStatus": PermissionProhibitionType,
            "ChannelType": ChannelType
        }
    )


@router.get("/quick_send.html", response_class=HTMLResponse)
async def quick_send_page(request: Request):

    # Передаём Enum-объекты в контекст
    return templates.TemplateResponse(
        request,
        name="quick_send.html",
        context={
            "page_title": "MSGPRO - О нас",
            "ConsentStatus": PermissionProhibitionType,
            "ChannelType": ChannelType
        }
    )

# http://127.0.0.1:8888/consent.html?action=allowed&phone=%2B79175729812


@router.get("/permission_prohibition.html", response_class=HTMLResponse)
async def consent_page(request: Request, db: Session = Depends(get_db)):
    action = request.query_params.get(
        "action", PermissionProhibitionType.BLOCKED.value
    )
    phone = request.query_params.get("phone")
    email = request.query_params.get("email")

    channel_identifier_translations = {
        "phone": "Телефон",
        "email": "Электронная почта",
        "telegram": "Telegram",
        "whatsapp": "WhatsApp",
    }

    message = ""
    channel = None
    value = None
    status_code=''
    if phone:
        channel = ChannelType.PHONE.value
        value = phone
    elif email:
        channel = ChannelType.EMAIL.value
        value = email

    service = PermissionProhibitionService(db)
    if channel and value:
        active_rule = service.get_permission_prohibition_by_is_default_channel_identifier_and_value(value, channel_identifier_name=channel)
        if active_rule and active_rule.status == PermissionProhibitionStatus.ACTIVE:
            if active_rule.type == action:
                rule_text = "разрешена" if action == PermissionProhibitionType.ALLOWED else "запрещена"
                message=f"Для данного контакта рассылка уже {rule_text}."
                status_code='-1'

    from app.services.channel_identifier import ChannelIdentifierService
    ci_service = ChannelIdentifierService(db)
    channel_identifiers = ci_service.get_default_channel_identifiers()

    return templates.TemplateResponse(
        request,
        name="permission_prohibition.html",
        context={
            "request": request,
            "page_title": "Управление рассылками",
            "action": action,
            "phone": phone,
            "email": email,
            "channel": channel,
            "value": value,
            "PermissionProhibitionType": PermissionProhibitionType,
            "ChannelType": ChannelType,
            "message": message,
            "translations": channel_identifier_translations,
            "channel_identifiers": channel_identifiers,
            "status_code":status_code
        }
    )
# --- ДИНАМИЧЕСКИЕ РОУТЫ (FastAPI проверяет их в последнюю очередь) ---

# Динамический обработчик для статических HTML страниц


@router.get("/{page_name}.html", response_class=HTMLResponse)
async def serve_static_pages(page_name: str):
    full_name = f"{page_name}.html"
    if full_name in VALID_PAGES:
        return FileResponse(f"app/templates/{full_name}")
    return HTMLResponse(content="Страница не найдена", status_code=404)


# Динамический обработчик для коротких ссылок-редиректов
@router.get("/{path}")
async def dynamic_redirects(path: str):
    if path in REDIRECT_MAP:
        return RedirectResponse(url=f"/{REDIRECT_MAP[path]}")
    return HTMLResponse(content="Маршрут не найден", status_code=404)
