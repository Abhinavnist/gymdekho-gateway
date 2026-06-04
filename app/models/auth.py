from pydantic import BaseModel, EmailStr, Field, model_validator
from pydantic import field_validator
import re


class RegisterRequest(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    full_name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None    # plain str — we validate format manually
    phone: str | None = None
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="MEMBER")
    city: str | None = None
    state: str | None = None

    @model_validator(mode="after")
    def email_or_phone_required(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required.")
        if self.role not in ("MEMBER", "GYM_OWNER", "TRAINER", "GYM_MANAGER"):
            raise ValueError("Invalid role for self-registration.")
        # Basic email format check (@ present)
        if self.email and "@" not in self.email:
            raise ValueError("Invalid email address.")
        return self


class LoginRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str

    @model_validator(mode="after")
    def email_or_phone_required(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required.")
        return self


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class VerifyEmailRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    uuid: str
    email: str | None
    phone: str | None
    full_name: str
    role: str
    profile_photo_url: str | None
    is_active: bool
    email_verified: bool
    created_at: str

    class Config:
        from_attributes = True
