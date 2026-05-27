from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_2fa_session_token,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.schemas.user import (
    ForgotPasswordRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    TwoFactorSetupOut,
    TwoFactorVerify,
    UserLogin,
    UserOut,
    UserRegister,
)
from app.services.email import send_password_reset
from app.services.two_factor import generate_secret, get_provisioning_uri, verify_code
from app.services.user import count_users, create_user, get_user_by_email, get_user_by_id, update_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    """Disponibile solo per creare il primo superadmin. Dopo, usa /admin/users."""
    total = await count_users(db)
    if total > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registrazione pubblica disabilitata. Contatta l'amministratore.",
        )
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata")

    user = await create_user(db, body.email, hash_password(body.password), body.name, role=UserRole.SUPERADMIN)
    return _tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabilitato")

    if user.two_factor_enabled:
        return TokenResponse(
            requires_2fa=True,
            session_token=create_2fa_session_token(str(user.id)),
        )

    return _tokens(user)


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa(body: TwoFactorVerify, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.session_token)
    if payload.get("type") != "2fa_session" or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Sessione 2FA non valida o scaduta")

    user = await get_user_by_id(db, int(payload["sub"]))
    if not user or not user.two_factor_enabled or not user.two_factor_secret:
        raise HTTPException(status_code=401, detail="Autenticazione 2FA non valida")

    if not verify_code(user.two_factor_secret, body.code):
        raise HTTPException(status_code=401, detail="Codice non valido")

    return _tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    user_id = payload.get("sub")
    if not user_id or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token non valido")
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


# ── 2FA Setup ─────────────────────────────────────────────────────────────────

@router.post("/2fa/setup", response_model=TwoFactorSetupOut)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Genera un nuovo segreto TOTP (non ancora attivo fino a /2fa/enable)."""
    secret = generate_secret()
    await update_user(db, current_user, two_factor_secret=secret)
    return TwoFactorSetupOut(secret=secret, uri=get_provisioning_uri(secret, current_user.email))


@router.post("/2fa/enable", response_model=UserOut)
async def enable_2fa(
    body: TwoFactorVerify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attiva il 2FA dopo aver verificato il primo codice."""
    if not current_user.two_factor_secret:
        raise HTTPException(400, "Esegui prima /auth/2fa/setup")
    if not verify_code(current_user.two_factor_secret, body.code):
        raise HTTPException(400, "Codice non valido")
    return await update_user(db, current_user, two_factor_enabled=True)


@router.post("/2fa/disable", response_model=UserOut)
async def disable_2fa(
    body: TwoFactorVerify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disattiva il 2FA dopo aver verificato l'ultimo codice valido."""
    if not current_user.two_factor_enabled or not current_user.two_factor_secret:
        raise HTTPException(400, "Il 2FA non è attivo")
    if not verify_code(current_user.two_factor_secret, body.code):
        raise HTTPException(400, "Codice non valido")
    return await update_user(db, current_user, two_factor_enabled=False, two_factor_secret=None)


# ── Password reset ────────────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=202)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Invia email di reset password. Risponde sempre 202 per non rivelare se l'email esiste."""
    user = await get_user_by_email(db, body.email)
    if user and user.is_active:
        token = create_password_reset_token(str(user.id))
        try:
            await send_password_reset(user.email, token)
        except Exception:
            pass  # non rivelare errori SMTP all'utente
    return {"detail": "Se l'email esiste, riceverai un link di reset."}


@router.post("/reset-password", status_code=200)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.token)
    if payload.get("type") != "password_reset" or not payload.get("sub"):
        raise HTTPException(400, "Link non valido o scaduto")
    user = await get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(400, "Link non valido o scaduto")
    await update_user(db, user, password_hash=hash_password(body.new_password))
    return {"detail": "Password aggiornata con successo."}
