"""Extended subscription queries for subscription management API."""
import secrets
import psycopg
from datetime import date, timedelta


async def get_plan_by_id(db: psycopg.AsyncConnection, plan_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute("SELECT * FROM subscription_plans WHERE id = %s AND is_active = TRUE", (plan_id,))
        return await cur.fetchone()


async def get_subscription_by_id(db: psycopg.AsyncConnection, sub_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT us.*, sp.plan_name, sp.plan_code, sp.max_leads_per_month,
                   sp.max_members, sp.max_whatsapp_messages, sp.features
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.id = %s
            """,
            (sub_id,),
        )
        return await cur.fetchone()


async def create_subscription(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO user_subscriptions (
                user_id, gym_id, plan_id, subscription_code, status,
                current_period_start, current_period_end,
                amount_per_cycle, total_amount, auto_renewal, next_billing_date
            ) VALUES (
                %(user_id)s, %(gym_id)s, %(plan_id)s, %(subscription_code)s, %(status)s,
                %(current_period_start)s, %(current_period_end)s,
                %(amount_per_cycle)s, %(total_amount)s, %(auto_renewal)s, %(next_billing_date)s
            )
            RETURNING *
            """,
            data,
        )
        return await cur.fetchone()


async def cancel_subscription(db: psycopg.AsyncConnection, sub_id: int, user_id: int, reason: str | None) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE user_subscriptions
            SET status = 'CANCELLED', cancellation_reason = %s,
                cancellation_date = CURRENT_DATE, cancelled_by = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s AND status IN ('ACTIVE','TRIAL')
            RETURNING *
            """,
            (reason, user_id, sub_id, user_id),
        )
        return await cur.fetchone()


async def get_payment_history(
    db: psycopg.AsyncConnection,
    user_id: int,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    offset = (page - 1) * limit
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT COUNT(*) AS total FROM payment_transactions WHERE user_id = %s",
            (user_id,),
        )
        total = (await cur.fetchone())["total"]

        await cur.execute(
            """
            SELECT pt.*, sp.plan_name
            FROM payment_transactions pt
            LEFT JOIN user_subscriptions us ON pt.subscription_id = us.id
            LEFT JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE pt.user_id = %s
            ORDER BY pt.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (user_id, limit, offset),
        )
        return await cur.fetchall(), total


async def create_payment_transaction(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO payment_transactions (
                user_id, subscription_id, transaction_id, transaction_type,
                amount, currency, base_amount, payment_method, payment_gateway,
                status, payment_date, description
            ) VALUES (
                %(user_id)s, %(subscription_id)s, %(transaction_id)s, %(transaction_type)s,
                %(amount)s, %(currency)s, %(base_amount)s, %(payment_method)s, %(payment_gateway)s,
                %(status)s, %(payment_date)s, %(description)s
            )
            RETURNING *
            """,
            data,
        )
        return await cur.fetchone()
