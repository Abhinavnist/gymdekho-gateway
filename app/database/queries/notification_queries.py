import psycopg


async def create_notification(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO notifications (
                user_id, notification_type, title, message,
                related_entity_type, related_entity_id,
                send_whatsapp, send_email, send_push, action_url
            ) VALUES (
                %(user_id)s, %(notification_type)s, %(title)s, %(message)s,
                %(related_entity_type)s, %(related_entity_id)s,
                %(send_whatsapp)s, %(send_email)s, %(send_push)s, %(action_url)s
            )
            RETURNING *
            """,
            data,
        )
        return await cur.fetchone()


async def get_user_notifications(
    db: psycopg.AsyncConnection,
    user_id: int,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    condition = "AND is_read = FALSE" if unread_only else ""
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"SELECT COUNT(*) AS total FROM notifications WHERE user_id = %s {condition}",
            (user_id,),
        )
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT * FROM notifications
            WHERE user_id = %s {condition}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (user_id, limit, offset),
        )
        rows = await cur.fetchall()
        return rows, total


async def mark_notifications_read(db: psycopg.AsyncConnection, user_id: int, notification_ids: list[int] | None = None) -> None:
    async with db.cursor() as cur:
        if notification_ids:
            await cur.execute(
                "UPDATE notifications SET is_read = TRUE, read_at = NOW() WHERE user_id = %s AND id = ANY(%s)",
                (user_id, notification_ids),
            )
        else:
            await cur.execute(
                "UPDATE notifications SET is_read = TRUE, read_at = NOW() WHERE user_id = %s AND is_read = FALSE",
                (user_id,),
            )


async def log_communication(db: psycopg.AsyncConnection, data: dict) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO communication_logs (
                gym_id, trainer_id, recipient_type, recipient_id,
                recipient_phone, recipient_email, recipient_name,
                communication_type, subject, message_content, status, purpose
            ) VALUES (
                %(gym_id)s, %(trainer_id)s, %(recipient_type)s, %(recipient_id)s,
                %(recipient_phone)s, %(recipient_email)s, %(recipient_name)s,
                %(communication_type)s, %(subject)s, %(message_content)s, %(status)s, %(purpose)s
            )
            """,
            data,
        )
