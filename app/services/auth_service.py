import json
import logging
from datetime import datetime, timedelta, timezone

import psycopg

from app.config import settings
from app.core.exceptions import (
    AccountLockedException,
    AlreadyExistsException,
    InvalidCredentialsException,
    NotFoundException,
    ValidationException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database.queries import user_queries
from app.utils.helpers import generate_random_token
from app.utils.email import send_email, otp_email_html, password_reset_email_html, welcome_email_html

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 30


async def register_user(db: psycopg.AsyncConnection, data: dict) -> dict:
    # Check duplicates
    if data.get("email"):
        existing = await user_queries.get_user_by_email(db, data["email"])
        if existing:
            raise AlreadyExistsException("Email")

    if data.get("phone"):
        existing = await user_queries.get_user_by_phone(db, data["phone"])
        if existing:
            raise AlreadyExistsException("Phone number")

    user_data = {
        "email": data.get("email"),
        "phone": data.get("phone"),
        "full_name": data["full_name"],
        "password_hash": hash_password(data["password"]),
        "role": data.get("role", "MEMBER"),
        "city": data.get("city"),
        "state": data.get("state"),
        "country": data.get("country", "India"),
        "zipcode": data.get("zipcode"),
        "notification_preferences": json.dumps({"email": True, "sms": False, "whatsapp": True}),
        "timezone": "Asia/Kolkata",
        "language_preference": "en",
    }

    user = await user_queries.create_user(db, user_data)

    # Set email verification token
    if user.get("email"):
        token = generate_random_token(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        await user_queries.set_email_verification_token(db, user["id"], token, expires_at)

    await db.commit()

    # Send welcome + verification email
    if user.get("email"):
        try:
            verify_link = f"{settings.frontend_url}/verify-email?token={token}"
            from app.utils.email import verification_email_html
            await send_email(
                user["email"],
                user["full_name"],
                "Verify your GymConnect AI email",
                verification_email_html(user["full_name"], verify_link),
            )
        except Exception:
            logger.warning("Failed to send verification email to %s", user.get("email"))

    return user


async def login_user(db: psycopg.AsyncConnection, email: str | None, phone: str | None, password: str) -> dict:
    user = None
    if email:
        user = await user_queries.get_user_by_email(db, email)
    elif phone:
        user = await user_queries.get_user_by_phone(db, phone)

    if not user:
        raise InvalidCredentialsException()

    # Check account lock
    if user.get("locked_until") and user["locked_until"] > datetime.now(timezone.utc):
        raise AccountLockedException()

    if not verify_password(password, user["password_hash"]):
        attempts = await user_queries.increment_failed_login(db, user["id"])
        await db.commit()
        if attempts >= MAX_FAILED_ATTEMPTS:
            locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCK_DURATION_MINUTES)
            await user_queries.lock_account(db, user["id"], locked_until)
            await db.commit()
            raise AccountLockedException()
        raise InvalidCredentialsException()

    if not user["is_active"]:
        raise InvalidCredentialsException()

    await user_queries.reset_failed_login(db, user["id"])
    await db.commit()

    token_payload = {"sub": str(user["id"]), "role": user["role"]}
    return {
        "access_token": create_access_token(token_payload),
        "refresh_token": create_refresh_token(token_payload),
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


async def refresh_access_token(db: psycopg.AsyncConnection, refresh_token: str) -> dict:
    from jose import JWTError
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValidationException("Invalid token type.")
        user_id = int(payload["sub"])
    except JWTError:
        raise ValidationException("Invalid or expired refresh token.")

    user = await user_queries.get_user_by_id(db, user_id)
    if not user or not user["is_active"]:
        raise NotFoundException("User")

    token_payload = {"sub": str(user["id"]), "role": user["role"]}
    return {
        "access_token": create_access_token(token_payload),
        "refresh_token": create_refresh_token(token_payload),
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


async def forgot_password(db: psycopg.AsyncConnection, email: str) -> None:
    user = await user_queries.get_user_by_email(db, email)
    if not user:
        return  # Silent fail — don't reveal whether email exists

    token = generate_random_token(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await user_queries.set_password_reset_token(db, user["id"], token, expires_at)
    await db.commit()

    reset_link = f"https://gymconnect.in/reset-password?token={token}"
    await send_email(
        email,
        user["full_name"],
        "Reset your GymConnect password",
        password_reset_email_html(user["full_name"], reset_link),
    )


async def reset_password(db: psycopg.AsyncConnection, token: str, new_password: str) -> None:
    user = await user_queries.get_user_by_reset_token(db, token)
    if not user:
        raise ValidationException("Invalid or expired reset token.")

    await user_queries.update_password(db, user["id"], hash_password(new_password))
    await user_queries.clear_password_reset_token(db, user["id"])
    await db.commit()


async def change_password(db: psycopg.AsyncConnection, user_id: int, current_password: str, new_password: str) -> None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        row = await cur.fetchone()

    if not row or not verify_password(current_password, row["password_hash"]):
        raise ValidationException("Current password is incorrect.")

    await user_queries.update_password(db, user_id, hash_password(new_password))
    await db.commit()
