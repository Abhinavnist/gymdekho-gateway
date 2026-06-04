import psycopg


async def get_platform_stats(db: psycopg.AsyncConnection) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM users WHERE is_active = TRUE) AS total_users,
                (SELECT COUNT(*) FROM gyms WHERE approval_status = 'APPROVED') AS approved_gyms,
                (SELECT COUNT(*) FROM gyms WHERE approval_status = 'PENDING') AS pending_gyms,
                (SELECT COUNT(*) FROM gym_members WHERE membership_status = 'ACTIVE') AS active_members,
                (SELECT COUNT(*) FROM chat_leads WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())) AS leads_this_month,
                (SELECT COUNT(*) FROM user_subscriptions WHERE status IN ('ACTIVE','TRIAL')) AS active_subscriptions,
                (SELECT COALESCE(SUM(amount), 0) FROM payment_transactions WHERE status = 'SUCCESS' AND DATE_TRUNC('month', payment_date) = DATE_TRUNC('month', NOW())) AS revenue_this_month,
                (SELECT COUNT(*) FROM users WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())) AS new_users_this_month
            """
        )
        return await cur.fetchone()


async def list_users(
    db: psycopg.AsyncConnection,
    role: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    offset = (page - 1) * limit
    conditions = []
    params: list = []

    if role:
        conditions.append("role = %s")
        params.append(role)
    if is_active is not None:
        conditions.append("is_active = %s")
        params.append(is_active)
    if search:
        conditions.append("(full_name ILIKE %s OR email ILIKE %s)")
        params += [f"%{search}%", f"%{search}%"]

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(f"SELECT COUNT(*) AS total FROM users {where}", params)
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT id, email, full_name, phone, role, is_active, email_verified,
                   failed_login_attempts, is_locked,
                   (locked_until IS NOT NULL AND locked_until > NOW()) AS is_currently_locked,
                   created_at, last_login_at
            FROM users {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        return await cur.fetchall(), total


async def get_user_detail(db: psycopg.AsyncConnection, user_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.phone, u.role, u.is_active,
                   u.email_verified, u.is_locked, u.created_at, u.last_login_at,
                   g.id AS gym_id, g.gym_name, g.approval_status
            FROM users u
            LEFT JOIN gyms g ON g.owner_user_id = u.id
            WHERE u.id = %s
            """,
            (user_id,),
        )
        return await cur.fetchone()


async def set_user_active(db: psycopg.AsyncConnection, user_id: int, is_active: bool) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "UPDATE users SET is_active = %s, updated_at = NOW() WHERE id = %s RETURNING id, email, full_name, is_active",
            (is_active, user_id),
        )
        return await cur.fetchone()


async def unlock_user(db: psycopg.AsyncConnection, user_id: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "UPDATE users SET is_locked = FALSE, locked_until = NULL, failed_login_attempts = 0, updated_at = NOW() WHERE id = %s RETURNING id, email, is_locked",
            (user_id,),
        )
        return await cur.fetchone()


async def list_gyms_admin(
    db: psycopg.AsyncConnection,
    approval_status: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    offset = (page - 1) * limit
    where = "WHERE approval_status = %s" if approval_status else ""
    params: list = ([approval_status] if approval_status else [])

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(f"SELECT COUNT(*) AS total FROM gyms {where}", params)
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT g.id, g.gym_name, g.city, g.state, g.gym_type, g.approval_status,
                   g.created_at, u.full_name AS owner_name, u.email AS owner_email, u.phone AS owner_phone
            FROM gyms g
            JOIN users u ON g.owner_user_id = u.id
            {where}
            ORDER BY g.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        return await cur.fetchall(), total


async def reject_gym(db: psycopg.AsyncConnection, gym_id: int, reason: str | None) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE gyms SET approval_status = 'REJECTED', rejection_reason = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, gym_name, approval_status
            """,
            (reason, gym_id),
        )
        return await cur.fetchone()


async def list_subscriptions_admin(
    db: psycopg.AsyncConnection,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    offset = (page - 1) * limit
    where = "WHERE us.status = %s" if status else ""
    params: list = ([status] if status else [])

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(f"SELECT COUNT(*) AS total FROM user_subscriptions us {where}", params)
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT us.id, us.status, us.current_period_start, us.current_period_end,
                   us.total_amount, us.leads_used, us.created_at,
                   sp.plan_name, sp.plan_code,
                   u.full_name AS user_name, u.email AS user_email,
                   g.gym_name
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            JOIN users u ON us.user_id = u.id
            LEFT JOIN gyms g ON us.gym_id = g.id
            {where}
            ORDER BY us.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        return await cur.fetchall(), total


async def get_system_settings(db: psycopg.AsyncConnection) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT setting_key, setting_value, setting_type, category, description, updated_at FROM system_settings ORDER BY category ASC, setting_key ASC"
        )
        return await cur.fetchall()


async def update_system_setting(db: psycopg.AsyncConnection, key: str, value: str) -> dict | None:
    import json
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        # Store as JSONB — wrap strings in quotes if not already valid JSON
        try:
            json.loads(value)
            json_value = value
        except (ValueError, TypeError):
            json_value = json.dumps(value)
        await cur.execute(
            "UPDATE system_settings SET setting_value = %s::jsonb, updated_at = NOW() WHERE setting_key = %s RETURNING setting_key, setting_value, setting_type, category, description",
            (json_value, key),
        )
        return await cur.fetchone()
