# app/core/security.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends,Request,Response
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.models import get_db
from app.config.config import settings
from app.crud.user import crud_user

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire,"created":datetime.now().isoformat()})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
    
# def get_token_from_cookie(request: Request) -> str:
#     token = request.cookies.get("access_token")
#     if not token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Not authenticated",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     return token

# здесь токен берется из заголовка HTTPOnly
# На клиенте при запросах с куками нужно указывать credentials: 'include'
# fetch('/api/v1/users/me', {
#     credentials: 'include'
# })
def get_current_user_from_httponly_cookies(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    # Сначала пробуем взять токен из заголовка
    if token is None:
        # Если нет, пробуем взять из cookie
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    phone = payload.get("sub")
    if not phone:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = crud_user.get_by_phone(db, phone=phone)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# здесь токен берется из обычного кука
async def get_current_user_from_cookies(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    phone = payload.get("sub")
    if not phone:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = crud_user.get_by_phone(db, phone=phone)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def set_HTTPOnly_Cookie(data:dict,token,name_cookie="access_token"):
    response = JSONResponse(data)
    response.set_cookie(
        key=name_cookie,
        value=token,
        httponly=True,
        secure=True,        # Только для HTTPS
        samesite="lax",     # Защита от CSRF
        max_age=60*60# пока сделал срок действия 1 час *24*7  # 7 дней (или используйте expires)
    )
    return response

def delete_HTTPOnly_Cookie(response: Response,name_cookie="access_token"):
    response.delete_cookie(
        key=name_cookie,
        path="/",
        secure=True,  # если используете HTTPS
        httponly=True,
        samesite="lax"
    )
    