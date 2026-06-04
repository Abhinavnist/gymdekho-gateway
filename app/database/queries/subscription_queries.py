import psycopg


async def get_all_plans(db: psycopg.AsyncConnection, target_type: str = "GYM") -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT * FROM subscription_plans
            WHERE is_active = TRUE AND (target_user_type = %s OR target_user_type = 'BOTH')
            ORDER BY sort_order ASC, base_price ASC
            """,
            (target_type,),
        )
        return await cur.fetchall()


async def get_gym_active_subscription(db: psycopg.AsyncConnection, gym_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT us.*, sp.plan_name, sp.max_leads_per_month, sp.max_members,
                   sp.max_whatsapp_messages, sp.features
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.gym_id = %s AND us.status IN ('ACTIVE', 'TRIAL')
            ORDER BY us.created_at DESC
            LIMIT 1
            """,
            (gym_id,),
        )
        return await cur.fetchone()


async def check_gym_lead_limit(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    """Returns current lead usage and plan limit so API can enforce it."""
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                sp.max_leads_per_month AS limit_leads,
                us.leads_used,
                (sp.max_leads_per_month = -1 OR us.leads_used < sp.max_leads_per_month) AS within_limit
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.gym_id = %s AND us.status IN ('ACTIVE', 'TRIAL')
            ORDER BY us.created_at DESC
            LIMIT 1
            """,
            (gym_id,),
        )
        row = await cur.fetchone()
        if not row:
            # No subscription = free tier, use default free limits
            await cur.execute(
                "SELECT max_leads_per_month FROM subscription_plans WHERE plan_code = 'GYM_STARTER' LIMIT 1",
            )
            plan = await cur.fetchone()
            leads_this_month = await _count_leads_this_month(cur, gym_id)
            limit = plan["max_leads_per_month"] if plan else 25
            return {
                "limit_leads": limit,
                "leads_used": leads_this_month,
                "within_limit": leads_this_month < limit,
            }
        return row


async def _count_leads_this_month(cur, gym_id: int) -> int:
    await cur.execute(
        "SELECT COUNT(*) AS cnt FROM chat_leads WHERE gym_id = %s AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())",
        (gym_id,),
    )
    return (await cur.fetchone())["cnt"]


async def increment_lead_usage(db: psycopg.AsyncConnection, gym_id: int) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE user_subscriptions SET leads_used = leads_used + 1 WHERE gym_id = %s AND status IN ('ACTIVE', 'TRIAL')",
            (gym_id,),
        )
