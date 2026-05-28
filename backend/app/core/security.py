from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, remember_me: bool = False) -> str:
    minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 48 if remember_me else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": subject, "exp": expire, "type": "access"}, settings.SECRET_KEY, settings.ALGORITHM)


def create_refresh_token(subject: str, remember_me: bool = False) -> str:
    days = settings.REFRESH_TOKEN_REMEMBER_ME_DAYS if remember_me else settings.REFRESH_TOKEN_EXPIRE_DAYS
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "refresh", "rem": remember_me},
        settings.SECRET_KEY,
        settings.ALGORITHM,
    )


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
