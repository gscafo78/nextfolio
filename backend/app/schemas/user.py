import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La password deve essere di almeno 8 caratteri")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    currency: str
    role: str
    two_factor_enabled: bool

    model_config = {"from_attributes": True}


class UserAdminOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    two_factor_enabled: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole = UserRole.USER

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La password deve essere di almeno 8 caratteri")
        return v


class UserAdminUpdate(BaseModel):
    name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    reset_2fa: bool = False


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    requires_2fa: bool = False
    session_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TwoFactorVerify(BaseModel):
    session_token: str
    code: str


class TwoFactorSetupOut(BaseModel):
    secret: str
    uri: str


class UserSettingsOut(BaseModel):
    theme: str
    display_currency: str
    zen_mode: bool
    language: str

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    theme: str | None = None
    display_currency: str | None = None
    zen_mode: bool | None = None
    language: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La password deve essere di almeno 8 caratteri")
        return v
