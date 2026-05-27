from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire, "type": "access"}, settings.SECRET_KEY, settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": subject, "exp": expire, "type": "refresh"}, settings.SECRET_KEY, settings.ALGORITHM)


def create_2fa_session_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "2fa_session"}, settings.SECRET_KEY, settings.ALGORITHM)


def create_password_reset_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "password_reset"}, settings.SECRET_KEY, settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return {}
