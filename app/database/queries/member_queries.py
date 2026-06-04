import psycopg


async def add_member(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO gym_members (
                gym_id, member_name, phone, email, date_of_birth, gender,
                address, emergency_contact_name, emergency_contact_phone,
                height_cm, weight_kg, fitness_goals, dietary_restrictions,
                referral_source, preferred_workout_time, interested_classes,
                whatsapp_notifications, email_notifications, notes, tags
            ) VALUES (
                %(gym_id)s, %(member_name)s, %(phone)s, %(email)s, %(date_of_birth)s, %(gender)s,
                %(address)s, %(emergency_contact_name)s, %(emergency_contact_phone)s,
                %(height_cm)s, %(weight_kg)s, %(fitness_goals)s, %(dietary_restrictions)s,
                %(referral_source)s, %(preferred_workout_time)s, %(interested_classes)s,
                %(whatsapp_notifications)s, %(email_notifications)s, %(notes)s, %(tags)s
            )
            RETURNING id, member_code, member_name, phone, membership_status, joined_date, created_at
            """,
            {**data, "gym_id": gym_id},
        )
        return await cur.fetchone()


async def get_member_by_id(db: psycopg.AsyncConnection, member_id: int, gym_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT m.*,
                   mh.start_date AS membership_start,
                   mh.end_date   AS membership_end,
                   mh.status     AS membership_status_detail,
                   gp.plan_name  AS current_plan_name,
                   gp.original_price AS plan_price
            FROM gym_members m
            LEFT JOIN membership_history mh ON mh.member_id = m.id AND mh.status = 'ACTIVE'
            LEFT JOIN gym_plans gp ON mh.plan_id = gp.id
            WHERE m.id = %s AND m.gym_id = %s
            """,
            (member_id, gym_id),
        )
        return await cur.fetchone()


async def get_members(
    db: psycopg.AsyncConnection,
    gym_id: int,
    search: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    conditions = ["m.gym_id = %s"]
    params: list = [gym_id]

    if search:
        conditions.append("(m.member_name ILIKE %s OR m.phone ILIKE %s OR m.email ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if status:
        conditions.append("m.membership_status = %s")
        params.append(status)

    where = " AND ".join(conditions)

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(f"SELECT COUNT(*) AS total FROM gym_members m WHERE {where}", params)
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT m.id, m.member_code, m.member_name, m.phone, m.email,
                   m.membership_status, m.joined_date, m.last_visit_date,
                   m.total_visits, m.is_active, m.whatsapp_notifications,
                   mh.end_date AS membership_end, gp.plan_name
            FROM gym_members m
            LEFT JOIN membership_history mh ON mh.member_id = m.id AND mh.status = 'ACTIVE'
            LEFT JOIN gym_plans gp ON mh.plan_id = gp.id
            WHERE {where}
            ORDER BY m.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        )
        rows = await cur.fetchall()
        return rows, total


async def update_member(db: psycopg.AsyncConnection, member_id: int, gym_id: int, data: dict) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE gym_members SET
                member_name = COALESCE(%(member_name)s, member_name),
                phone = COALESCE(%(phone)s, phone),
                email = COALESCE(%(email)s, email),
                notes = COALESCE(%(notes)s, notes),
                tags = COALESCE(%(tags)s, tags),
                fitness_goals = COALESCE(%(fitness_goals)s, fitness_goals),
                updated_at = NOW()
            WHERE id = %(member_id)s AND gym_id = %(gym_id)s
            RETURNING id, member_code, member_name, phone, updated_at
            """,
            {
                "member_name": None, "phone": None, "email": None,
                "notes": None, "tags": None, "fitness_goals": None,
                **data,
                "member_id": member_id, "gym_id": gym_id,
            },
        )
        return await cur.fetchone()


async def update_member_status(db: psycopg.AsyncConnection, member_id: int, gym_id: int, status: str) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE gym_members SET membership_status = %s, updated_at = NOW() WHERE id = %s AND gym_id = %s",
            (status, member_id, gym_id),
        )


async def get_members_with_whatsapp_enabled(db: psycopg.AsyncConnection, gym_id: int) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT id, member_name, phone
            FROM gym_members
            WHERE gym_id = %s AND whatsapp_notifications = TRUE AND is_active = TRUE AND phone IS NOT NULL
            """,
            (gym_id,),
        )
        return await cur.fetchall()


async def get_expiring_memberships(db: psycopg.AsyncConnection, gym_id: int, days_ahead: int = 7) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT m.id, m.member_name, m.phone, m.email,
                   mh.end_date, gp.plan_name
            FROM gym_members m
            JOIN membership_history mh ON mh.member_id = m.id AND mh.status = 'ACTIVE'
            JOIN gym_plans gp ON mh.plan_id = gp.id
            WHERE m.gym_id = %s
              AND mh.end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '%s days'
              AND m.is_active = TRUE
            ORDER BY mh.end_date ASC
            """,
            (gym_id, days_ahead),
        )
        return await cur.fetchall()


async def add_membership(db: psycopg.AsyncConnection, member_id: int, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        # Deactivate existing active membership first
        await cur.execute(
            "UPDATE membership_history SET status = 'EXPIRED' WHERE member_id = %s AND status = 'ACTIVE'",
            (member_id,),
        )
        await cur.execute(
            """
            INSERT INTO membership_history (
                member_id, plan_id, start_date, end_date,
                plan_price, discount_applied, total_amount,
                payment_method, payment_status, payment_date,
                trainer_sessions_allocated, created_by
            ) VALUES (
                %(member_id)s, %(plan_id)s, %(start_date)s, %(end_date)s,
                %(plan_price)s, %(discount_applied)s, %(total_amount)s,
                %(payment_method)s, %(payment_status)s, %(payment_date)s,
                %(trainer_sessions_allocated)s, %(created_by)s
            )
            RETURNING *
            """,
            {**data, "member_id": member_id},
        )
        return await cur.fetchone()


async def get_member_dashboard_stats(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                COUNT(*) AS total_members,
                COUNT(*) FILTER (WHERE membership_status = 'ACTIVE') AS active_members,
                COUNT(*) FILTER (WHERE membership_status = 'INACTIVE') AS inactive_members,
                COUNT(*) FILTER (WHERE membership_status = 'EXPIRED') AS expired_members,
                COUNT(*) FILTER (WHERE membership_status = 'SUSPENDED') AS suspended_members,
                COUNT(*) FILTER (WHERE DATE_TRUNC('month', joined_date) = DATE_TRUNC('month', CURRENT_DATE)) AS new_this_month,
                (SELECT COUNT(*) FROM membership_history mh WHERE mh.member_id IN (SELECT id FROM gym_members WHERE gym_id = %s) AND mh.end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7) AS expiring_this_week
            FROM gym_members
            WHERE gym_id = %s
            """,
            (gym_id, gym_id),
        )
        return await cur.fetchone()
