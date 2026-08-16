# app/web/routes.py
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()

# Если вы хотите использовать Jinja2 для динамических данных (например, год)
templates = Jinja2Templates(directory="app/templates")
templates.env.auto_reload = True
templates.env.cache_size = 0

# Маршруты для страниц (используем FileResponse для простоты, но можно и Jinja2)
# @router.get("/", response_class=HTMLResponse)
# async def index():
#     return FileResponse("index.html")

@router.get("/quick_send.html", response_class=HTMLResponse)
async def quick_send():
    return FileResponse("app/templates/quick_send.html")

@router.get("/about.html", response_class=HTMLResponse)
async def about():
    return FileResponse("app/templates/about.html")

@router.get("/contact.html", response_class=HTMLResponse)
async def contact():
    return FileResponse("app/templates/contact.html")

@router.get("/terms.html", response_class=HTMLResponse)
async def terms():
    return FileResponse("app/templates/terms.html")

@router.get("/privacy.html", response_class=HTMLResponse)
async def privacy():
    return FileResponse("app/templates/privacy.html")

@router.get("/login.html", response_class=HTMLResponse)
async def login():
    return FileResponse("app/templates/login.html")

@router.get("/signup.html", response_class=HTMLResponse)
async def signup():
    return FileResponse("app/templates/signup.html")

# Редиректы для удобства (короткие URL)
@router.get("/quick-send")
async def quick_send_redirect():
    return RedirectResponse(url="/quick_send.html")

@router.get("/about")
async def about_redirect():
    return RedirectResponse(url="/about-us-v1.html")

@router.get("/contact")
async def contact_redirect():
    return RedirectResponse(url="/contact-v1.html")

@router.get("/terms")
async def terms_redirect():
    return RedirectResponse(url="/terms.html")

@router.get("/privacy")
async def privacy_redirect():
    return RedirectResponse(url="/privacy.html")

@router.get("/login")
async def login_redirect():
    return RedirectResponse(url="/login.html")

@router.get("/register")
async def register_redirect():
    return RedirectResponse(url="/signup.html")