# main.py
import uvicorn
from fastapi import FastAPI,Request
from fastapi.responses import FileResponse
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse,PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException
from app.models.models import engine, Base
from app.api.v1 import auth, consent, messages, users,admin
from app.web.routes import router as web_router

# Создаём таблицы (если ещё не созданы)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MSGPRO.RU API",
    description="Бесплатный сервис для отправки СМС и email",
    version="1.0.0"
)

# Настройка CORS
origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://msgpro.ru",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статики (CSS, JS, images)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

    
# Подключение API-роутеров
app.include_router(auth.router, prefix="/api/v1")
app.include_router(consent.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1") 

# Подключение веб-роутера (страницы)
app.include_router(web_router)



if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8888, reload=True)