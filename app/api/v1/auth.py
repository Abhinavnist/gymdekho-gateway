from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel
from app.core.dependencies import DBConn, CurrentUser
from app.models.auth import (
    RegisterRequest, LoginRequest, RefreshTokenRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest,
)
from app.services import auth_service
from app.database.queries import user_queries
from app.utils.response import success_response

router = APIRouter(prefix="/auth", tags=["Authentication"])


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    bio: str | None = None
    city: str | None = None
    state: str | None = None


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: DBConn):
    user = await auth_service.register_user(db, body.model_dump())
    return success_response(user, "Registration successful.", 201)


@router.post("/login")
async def login(body: LoginRequest, db: DBConn):
    tokens = await auth_service.login_user(db, body.email, body.phone, body.password)
    return success_response(tokens, "Login successful.")


@router.post("/refresh-token")
async def refresh_token(body: RefreshTokenRequest, db: DBConn):
    tokens = await auth_service.refresh_access_token(db, body.refresh_token)
    return success_response(tokens)


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: DBConn):
    await auth_service.forgot_password(db, body.email)
    return success_response(message="If that email exists, a reset link has been sent.")


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: DBConn):
    await auth_service.reset_password(db, body.token, body.new_password)
    return success_response(message="Password reset successfully.")


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, db: DBConn, current_user: CurrentUser):
    await auth_service.change_password(db, current_user["id"], body.current_password, body.new_password)
    return success_response(message="Password changed successfully.")


@router.get("/me")
async def get_me(current_user: CurrentUser):
    return success_response(current_user)


@router.put("/me")
async def update_profile(body: ProfileUpdateRequest, db: DBConn, current_user: CurrentUser):
    updated = await user_queries.update_user_profile(db, current_user["id"], body.model_dump(exclude_none=True))
    await db.commit()
    return success_response(updated)


@router.post("/me/photo")
async def upload_profile_photo(db: DBConn, current_user: CurrentUser, file: UploadFile = File(...)):
    from app.utils.file_upload import upload_image
    content = await file.read()
    result = await upload_image(content, file.content_type, folder="users/photos", public_id=f"user_{current_user['id']}")
    await user_queries.update_profile_photo(db, current_user["id"], result["url"])
    await db.commit()
    return success_response({"profile_photo_url": result["url"]})


@router.post("/verify-email")
async def verify_email(token: str, db: DBConn):
    """Verify email using token sent to the user's inbox."""
    from app.core.exceptions import ValidationException
    user = await user_queries.get_user_by_verification_token(db, token)
    if not user:
        raise ValidationException("Invalid or expired verification token.")
    await user_queries.set_email_verified(db, user["id"])
    await db.commit()
    return success_response(message="Email verified successfully.")


@router.post("/resend-verification")
async def resend_verification(db: DBConn, current_user: CurrentUser):
    """Resend verification email to the logged-in user."""
    from app.core.exceptions import ValidationException
    from app.utils.helpers import generate_random_token
    from app.utils.email import verification_email_html, send_email
    from datetime import datetime, timedelta, timezone
    from app.config import settings

    if current_user.get("email_verified"):
        raise ValidationException("Email is already verified.")
    if not current_user.get("email"):
        raise ValidationException("No email address on your account.")

    token = generate_random_token(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await user_queries.set_email_verification_token(db, current_user["id"], token, expires_at)
    await db.commit()

    verify_link = f"{settings.frontend_url}/verify-email?token={token}"
    await send_email(
        current_user["email"],
        current_user["full_name"],
        "Verify your GymConnect AI email",
        verification_email_html(current_user["full_name"], verify_link),
    )
    return success_response(message="Verification email sent.")
