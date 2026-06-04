import psycopg
from datetime import datetime, timezone


async def get_user_by_id(db: psycopg.AsyncConnection, user_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT id, uuid, email, phone, full_name, role, profile_photo_url,
                   is_active, is_locked, email_verified, phone_verified, profile_completed,
                   city, state, country, bio, gender,
                   failed_login_attempts, locked_until, last_login_at,
                   notification_preferences, timezone, language_preference,
                   created_at, updated_at
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        return await cur.fetchone()


async def get_user_by_email(db: psycopg.AsyncConnection, email: str) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT id, uuid, email, phone, full_name, role, password_hash,
                   is_active, is_locked, email_verified, failed_login_attempts, locked_until
            FROM users
            WHERE LOWER(email) = LOWER(%s)
            """,
            (email,),
        )
        return await cur.fetchone()


async def get_user_by_phone(db: psycopg.AsyncConnection, phone: str) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT id, uuid, email, phone, full_name, role, password_hash, is_active, is_locked FROM users WHERE phone = %s",
            (phone,),
        )
        return await cur.fetchone()


async def create_user(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO users (
                email, phone, full_name, password_hash, role,
                city, state, country, zipcode,
                notification_preferences, timezone, language_preference
            ) VALUES (
                %(email)s, %(phone)s, %(full_name)s, %(password_hash)s, %(role)s,
                %(city)s, %(state)s, %(country)s, %(zipcode)s,
                %(notification_preferences)s, %(timezone)s, %(language_preference)s
            )
            RETURNING id, uuid, email, phone, full_name, role, is_active, email_verified, created_at
            """,
            data,
        )
        return await cur.fetchone()


async def update_user_profile(db: psycopg.AsyncConnection, user_id: int, data: dict) -> dict | None:
    # Build SET clause dynamically from only the fields provided
    allowed = {"full_name", "phone", "date_of_birth", "gender", "bio", "city", "state", "country", "zipcode"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        # Nothing to update — just return current user
        async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                "SELECT id, uuid, email, phone, full_name, role, city, state, bio, gender, updated_at FROM users WHERE id = %s",
                (user_id,),
            )
            return await cur.fetchone()

    set_clause = ", ".join(f"{col} = %({col})s" for col in fields)
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"""
            UPDATE users SET {set_clause}, updated_at = NOW()
            WHERE id = %(user_id)s
            RETURNING id, uuid, email, phone, full_name, role, city, state, bio, gender, updated_at
            """,
            {**fields, "user_id": user_id},
        )
        return await cur.fetchone()


async def update_profile_photo(db: psycopg.AsyncConnection, user_id: int, photo_url: str) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET profile_photo_url = %s, updated_at = NOW() WHERE id = %s",
            (photo_url, user_id),
        )


async def update_password(db: psycopg.AsyncConnection, user_id: int, password_hash: str) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
            (password_hash, user_id),
        )


async def increment_failed_login(db: psycopg.AsyncConnection, user_id: int) -> int:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = %s RETURNING failed_login_attempts",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["failed_login_attempts"]


async def lock_account(db: psycopg.AsyncConnection, user_id: int, locked_until: datetime) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET is_locked = TRUE, locked_until = %s WHERE id = %s",
            (locked_until, user_id),
        )


async def reset_failed_login(db: psycopg.AsyncConnection, user_id: int) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET failed_login_attempts = 0, is_locked = FALSE, locked_until = NULL, last_login_at = NOW() WHERE id = %s",
            (user_id,),
        )


# ─── Email Verification ───────────────────────────────────────────────────────

async def set_email_verification_token(db: psycopg.AsyncConnection, user_id: int, token: str, expires_at: datetime) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET email_verification_token = %s, email_verification_expires_at = %s WHERE id = %s",
            (token, expires_at, user_id),
        )


async def get_user_by_verification_token(db: psycopg.AsyncConnection, token: str) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT id, email, full_name, email_verification_expires_at
            FROM users
            WHERE email_verification_token = %s AND email_verification_expires_at > NOW()
            """,
            (token,),
        )
        return await cur.fetchone()


async def set_email_verified(db: psycopg.AsyncConnection, user_id: int) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET email_verified = TRUE,
                email_verification_token = NULL,
                email_verification_expires_at = NULL,
                updated_at = NOW()
            WHERE id = %s
            """,
            (user_id,),
        )


async def resend_verification_email(db: psycopg.AsyncConnection, user_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT id, email, full_name, email_verified FROM users WHERE id = %s",
            (user_id,),
        )
        return await cur.fetchone()


# ─── Password Reset ───────────────────────────────────────────────────────────

async def set_password_reset_token(db: psycopg.AsyncConnection, user_id: int, token: str, expires_at: datetime) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET password_reset_token = %s, password_reset_expires_at = %s WHERE id = %s",
            (token, expires_at, user_id),
        )


async def get_user_by_reset_token(db: psycopg.AsyncConnection, token: str) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT id, email, full_name, password_reset_expires_at
            FROM users
            WHERE password_reset_token = %s AND password_reset_expires_at > NOW()
            """,
            (token,),
        )
        return await cur.fetchone()


async def clear_password_reset_token(db: psycopg.AsyncConnection, user_id: int) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET password_reset_token = NULL, password_reset_expires_at = NULL WHERE id = %s",
            (user_id,),
        )


async def deactivate_user(db: psycopg.AsyncConnection, user_id: int) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = %s",
            (user_id,),
        )
