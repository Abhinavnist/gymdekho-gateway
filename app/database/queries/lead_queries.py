import psycopg


async def create_lead(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO chat_leads (
                gym_id, trainer_id, lead_name, phone, email, age_range, gender, location,
                initial_query, chat_transcript, lead_source,
                interested_services, budget_range, preferred_timing, fitness_goals,
                utm_source, utm_medium, utm_campaign,
                prefers_whatsapp, prefers_email, lead_score
            ) VALUES (
                %(gym_id)s, %(trainer_id)s, %(lead_name)s, %(phone)s, %(email)s,
                %(age_range)s, %(gender)s, %(location)s,
                %(initial_query)s, %(chat_transcript)s, %(lead_source)s,
                %(interested_services)s, %(budget_range)s, %(preferred_timing)s, %(fitness_goals)s,
                %(utm_source)s, %(utm_medium)s, %(utm_campaign)s,
                %(prefers_whatsapp)s, %(prefers_email)s, %(lead_score)s
            )
            RETURNING id, lead_name, phone, status, lead_score, created_at
            """,
            data,
        )
        return await cur.fetchone()


async def get_lead_by_id(db: psycopg.AsyncConnection, lead_id: int, gym_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT l.*,
                   u.full_name AS assigned_to_name
            FROM chat_leads l
            LEFT JOIN users u ON l.assigned_to = u.id
            WHERE l.id = %s AND l.gym_id = %s
            """,
            (lead_id, gym_id),
        )
        return await cur.fetchone()


async def get_leads(
    db: psycopg.AsyncConnection,
    gym_id: int,
    status: str | None = None,
    search: str | None = None,
    priority: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    conditions = ["l.gym_id = %s"]
    params: list = [gym_id]

    if status:
        conditions.append("l.status = %s")
        params.append(status)
    if priority:
        conditions.append("l.priority = %s")
        params.append(priority)
    if search:
        conditions.append("(l.lead_name ILIKE %s OR l.phone ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions)

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(f"SELECT COUNT(*) AS total FROM chat_leads l WHERE {where}", params)
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT l.id, l.lead_name, l.phone, l.email, l.status, l.priority,
                   l.lead_score, l.lead_source, l.follow_up_date, l.converted_to_member,
                   l.contact_attempts, l.last_contact_date, l.created_at,
                   u.full_name AS assigned_to_name
            FROM chat_leads l
            LEFT JOIN users u ON l.assigned_to = u.id
            WHERE {where}
            ORDER BY l.lead_score DESC, l.created_at DESC
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        )
        rows = await cur.fetchall()
        return rows, total


async def update_lead_status(db: psycopg.AsyncConnection, lead_id: int, gym_id: int, status: str) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE chat_leads SET status = %s, updated_at = NOW() WHERE id = %s AND gym_id = %s",
            (status, lead_id, gym_id),
        )


async def update_lead(db: psycopg.AsyncConnection, lead_id: int, gym_id: int, data: dict) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE chat_leads SET
                status = COALESCE(%(status)s, status),
                priority = COALESCE(%(priority)s, priority),
                assigned_to = COALESCE(%(assigned_to)s, assigned_to),
                follow_up_date = COALESCE(%(follow_up_date)s, follow_up_date),
                follow_up_notes = COALESCE(%(follow_up_notes)s, follow_up_notes),
                contact_attempts = contact_attempts + COALESCE(%(increment_contact)s, 0),
                last_contact_date = CASE WHEN %(increment_contact)s > 0 THEN CURRENT_DATE ELSE last_contact_date END,
                updated_at = NOW()
            WHERE id = %(lead_id)s AND gym_id = %(gym_id)s
            RETURNING id, lead_name, status, priority, follow_up_date
            """,
            {
                "status": None, "priority": None, "assigned_to": None,
                "follow_up_date": None, "follow_up_notes": None, "increment_contact": 0,
                **data,
                "lead_id": lead_id, "gym_id": gym_id,
                "increment_contact": data.get("increment_contact") or 0,
            },
        )
        return await cur.fetchone()


async def convert_lead_to_member(
    db: psycopg.AsyncConnection,
    lead_id: int,
    gym_id: int,
    member_id: int,
) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            """
            UPDATE chat_leads SET
                converted_to_member = TRUE,
                member_id = %s,
                conversion_date = CURRENT_DATE,
                status = 'CONVERTED',
                updated_at = NOW()
            WHERE id = %s AND gym_id = %s
            """,
            (member_id, lead_id, gym_id),
        )


async def add_lead_interaction(db: psycopg.AsyncConnection, lead_id: int, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO lead_interactions (
                lead_id, user_id, interaction_type, subject, content, outcome, next_action, next_action_date
            ) VALUES (
                %(lead_id)s, %(user_id)s, %(interaction_type)s, %(subject)s, %(content)s,
                %(outcome)s, %(next_action)s, %(next_action_date)s
            )
            RETURNING *
            """,
            {**data, "lead_id": lead_id},
        )
        return await cur.fetchone()


async def get_lead_interactions(db: psycopg.AsyncConnection, lead_id: int) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT li.*, u.full_name AS added_by_name
            FROM lead_interactions li
            LEFT JOIN users u ON li.user_id = u.id
            WHERE li.lead_id = %s
            ORDER BY li.interaction_date DESC
            """,
            (lead_id,),
        )
        return await cur.fetchall()


async def get_leads_dashboard_stats(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                COUNT(*) AS total_leads,
                COUNT(*) FILTER (WHERE status = 'NEW') AS new_leads,
                COUNT(*) FILTER (WHERE status = 'CONVERTED') AS converted,
                COUNT(*) FILTER (WHERE status = 'LOST') AS lost,
                COUNT(*) FILTER (WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())) AS this_month,
                COUNT(*) FILTER (WHERE follow_up_date = CURRENT_DATE) AS follow_ups_today,
                ROUND(
                    COUNT(*) FILTER (WHERE status = 'CONVERTED')::NUMERIC /
                    NULLIF(COUNT(*), 0) * 100, 2
                ) AS conversion_rate
            FROM chat_leads
            WHERE gym_id = %s
            """,
            (gym_id,),
        )
        return await cur.fetchone()
