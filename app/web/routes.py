from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.models.models import get_db,ChannelType,ConsentStatus, ContactType
from app.services.consent import ConsentService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Список существующих статических файлов
VALID_PAGES = {
   "quick_send.html", 
    "terms.html", "privacy.html", 
    "login.html", "signup.html"
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
    "consent": f"consent.html?action={ConsentStatus.BLOCKED.value}",
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
            "ConsentStatus": ConsentStatus,  # передаём весь Enum
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
            "ConsentStatus": ConsentStatus, 
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
            "ConsentStatus": ConsentStatus, 
            "ChannelType": ChannelType
        }
    )
# http://127.0.0.1:8888/consent.html?action=allowed&phone=%2B79175729812
@router.get("/consent.html", response_class=HTMLResponse)
async def consent_page(request: Request, db: Session = Depends(get_db)):
    # Получаем параметры из URL
    action = request.query_params.get("action", ConsentStatus.BLOCKED.value)  # значение по умолчанию
    phone = request.query_params.get("phone")
    email = request.query_params.get("email")
    message=""
    # Определяем канал и значение
    if phone:
        channel = ChannelType.PHONE.value
        value = phone
    elif email:
        channel = ChannelType.EMAIL.value
        value = email
    else:
        channel = None
        value = None
    service=ConsentService(db)
    if channel and value:
        consent=service.get_consent_by_channel_code_and_value(value,channel_code=channel)
        if not consent:
            if channel == ContactType.EMAIL:
                message="Нет запрета на рассылку с нашего сервиса на указанный email"
            elif channel == ContactType.PHONE:
                message="Нет запрета на рассылку СМС с нашего сервиса на указанный телефон"
        if consent and consent.status==ConsentStatus.ALLOWED:
            if channel == ContactType.EMAIL:
                message="Есть разрешение на рассылку с нашего сервиса на указанный email"
            elif channel == ContactType.PHONE:
                message="Есть разрешение на рассылку СМС с нашего сервиса на указанный телефон"
        if consent and consent.status==ConsentStatus.BLOCKED:
            if channel == ContactType.EMAIL:
                message="Ранее был установлен запрет рассылки писем с нашего сервиса на указанный email"
            elif channel == ContactType.PHONE:
                message="Ранее был установлен запрет рассылки СМС с нашего сервиса на указанный телефон"
    # Передаём Enum-объекты в контекст
    return templates.TemplateResponse(
        request,
        name="consent.html",
        context={
            "page_title": "Управление согласием",#"Запрет рассылки" if action == ConsentStatus.BLOCKED.value else "Разрешение рассылки",
            "action": action,
            "channel": channel,
            "value": value,
            "ConsentStatus": ConsentStatus,  # передаём весь Enum
            "ChannelType": ChannelType,
            "message":message
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
