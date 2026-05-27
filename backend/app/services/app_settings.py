import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings
from app.models.user import User

_otp_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

_KEY_PUBLIC_REG = "allow_public_registration"


async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(AppSettings(key=key, value=value))
    await db.commit()


async def is_public_registration_allowed(db: AsyncSession) -> bool:
    val = await get_setting(db, _KEY_PUBLIC_REG, "false")
    return val.lower() == "true"


async def set_public_registration(db: AsyncSession, allowed: bool) -> None:
    await set_setting(db, _KEY_PUBLIC_REG, "true" if allowed else "false")


# ── OTP ───────────────────────────────────────────────────────────────────────

def generate_otp() -> tuple[str, str]:
    """Restituisce (code_plain, code_hash). Il codice è 6 cifre zero-padded."""
    code = str(secrets.randbelow(1_000_000)).zfill(6)
    return code, _otp_ctx.hash(code)


def verify_otp(plain: str, hashed: str) -> bool:
    return _otp_ctx.verify(plain, hashed)


async def set_verification_token(db: AsyncSession, user: User, token_hash: str) -> None:
    user.email_verified = False
    user.email_verification_token = token_hash
    user.email_verification_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db.commit()
    await db.refresh(user)


async def clear_verification_token(db: AsyncSession, user: User) -> None:
    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    await db.commit()
    await db.refresh(user)
