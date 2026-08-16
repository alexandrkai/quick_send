from fastapi import FastAPI
from app.api.v1.endpoints import router as api_router

app = FastAPI(title="MSGPRO API", version="1.0")

app.include_router(api_router)