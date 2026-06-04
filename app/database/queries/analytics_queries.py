import psycopg


async def get_gym_dashboard_stats(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM gym_members WHERE gym_id = %s) AS total_members,
                (SELECT COUNT(*) FROM gym_members WHERE gym_id = %s AND membership_status = 'ACTIVE') AS active_members,
                (SELECT COUNT(*) FROM gym_members WHERE gym_id = %s AND DATE_TRUNC('month', joined_date) = DATE_TRUNC('month', NOW())) AS new_members_this_month,
                (SELECT COUNT(*) FROM chat_leads WHERE gym_id = %s) AS total_leads,
                (SELECT COUNT(*) FROM chat_leads WHERE gym_id = %s AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())) AS new_leads_this_month,
                (SELECT COUNT(*) FROM chat_leads WHERE gym_id = %s AND status = 'NEW') AS pending_leads,
                (SELECT COUNT(*) FROM gym_visits WHERE gym_id = %s AND visit_date = CURRENT_DATE) AS checkins_today,
                (SELECT COUNT(*) FROM membership_history mh JOIN gym_members m ON mh.member_id = m.id WHERE m.gym_id = %s AND mh.end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7) AS expiring_this_week,
                (SELECT COALESCE(SUM(mh.total_amount), 0) FROM membership_history mh JOIN gym_members m ON mh.member_id = m.id WHERE m.gym_id = %s AND mh.payment_status = 'PAID' AND DATE_TRUNC('month', mh.payment_date) = DATE_TRUNC('month', NOW())) AS revenue_this_month,
                (SELECT page_views_count FROM gyms WHERE id = %s) AS total_page_views
            """,
            (gym_id,) * 10,
        )
        return await cur.fetchone()


async def get_monthly_member_growth(db: psycopg.AsyncConnection, gym_id: int, months: int = 6) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', NOW()) - ((%s - 1) || ' months')::interval,
                    DATE_TRUNC('month', NOW()),
                    '1 month'::interval
                ) AS month_start
            )
            SELECT
                TO_CHAR(m.month_start, 'Mon YY') AS month,
                COALESCE(COUNT(gm.id), 0) AS new_members,
                (SELECT COUNT(*) FROM gym_members gm2 WHERE gm2.gym_id = %s AND gm2.joined_date < m.month_start + '1 month'::interval) AS total_active
            FROM months m
            LEFT JOIN gym_members gm ON gm.gym_id = %s AND DATE_TRUNC('month', gm.joined_date) = m.month_start
            GROUP BY m.month_start
            ORDER BY m.month_start ASC
            """,
            (months, gym_id, gym_id),
        )
        return await cur.fetchall()


async def get_lead_funnel(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                COUNT(*) AS total_leads,
                COUNT(*) FILTER (WHERE status IN ('CONTACTED','INTERESTED','DEMO_SCHEDULED','CONVERTED')) AS contacted,
                COUNT(*) FILTER (WHERE status IN ('INTERESTED','DEMO_SCHEDULED','CONVERTED')) AS interested,
                COUNT(*) FILTER (WHERE status IN ('DEMO_SCHEDULED','CONVERTED')) AS demo_scheduled,
                COUNT(*) FILTER (WHERE status = 'CONVERTED') AS converted
            FROM chat_leads
            WHERE gym_id = %s
            """,
            (gym_id,),
        )
        row = await cur.fetchone()
        if not row:
            return {"total_leads": 0, "contacted": 0, "interested": 0, "demo_scheduled": 0, "converted": 0, "conversion_rate": 0}
        total = row["total_leads"] or 0
        converted = row["converted"] or 0
        return {
            **row,
            "conversion_rate": round((converted / total * 100), 1) if total > 0 else 0,
        }


async def get_revenue_summary(db: psycopg.AsyncConnection, gym_id: int, months: int = 3) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', NOW()) - ((%s - 1) || ' months')::interval,
                    DATE_TRUNC('month', NOW()),
                    '1 month'::interval
                ) AS month_start
            )
            SELECT
                TO_CHAR(m.month_start, 'Mon YY') AS month,
                COALESCE(SUM(mh.total_amount), 0) AS revenue,
                COUNT(mh.id) AS transactions
            FROM months m
            LEFT JOIN membership_history mh ON DATE_TRUNC('month', mh.payment_date) = m.month_start
                AND mh.payment_status = 'PAID'
                AND mh.member_id IN (SELECT id FROM gym_members WHERE gym_id = %s)
            GROUP BY m.month_start
            ORDER BY m.month_start ASC
            """,
            (months, gym_id),
        )
        return await cur.fetchall()
