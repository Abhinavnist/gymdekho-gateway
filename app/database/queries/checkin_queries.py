import psycopg


async def check_in(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO gym_visits (member_id, gym_id, visit_type, purpose, entry_method, facilities_used)
            VALUES (%(member_id)s, %(gym_id)s, %(visit_type)s, %(purpose)s, %(entry_method)s, %(facilities_used)s)
            RETURNING *
            """,
            data,
        )
        return await cur.fetchone()


async def check_out(db: psycopg.AsyncConnection, visit_id: int, gym_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE gym_visits
            SET check_out_time = NOW()
            WHERE id = %s AND gym_id = %s AND check_out_time IS NULL
            RETURNING *
            """,
            (visit_id, gym_id),
        )
        return await cur.fetchone()


async def get_active_visit(db: psycopg.AsyncConnection, member_id: int, gym_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT * FROM gym_visits
            WHERE member_id = %s AND gym_id = %s AND check_out_time IS NULL
            ORDER BY check_in_time DESC
            LIMIT 1
            """,
            (member_id, gym_id),
        )
        return await cur.fetchone()


async def get_gym_visits(
    db: psycopg.AsyncConnection,
    gym_id: int,
    date_filter: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict], int]:
    offset = (page - 1) * limit
    date_clause = "AND v.visit_date = %s::DATE" if date_filter else ""
    params_count = [gym_id]
    params_list = [gym_id]
    if date_filter:
        params_count.append(date_filter)
        params_list.append(date_filter)
    params_list += [limit, offset]

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"SELECT COUNT(*) AS total FROM gym_visits v WHERE v.gym_id = %s {date_clause}",
            params_count,
        )
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT v.*, m.member_name, m.member_code, m.phone
            FROM gym_visits v
            JOIN gym_members m ON v.member_id = m.id
            WHERE v.gym_id = %s {date_clause}
            ORDER BY v.check_in_time DESC
            LIMIT %s OFFSET %s
            """,
            params_list,
        )
        return await cur.fetchall(), total


async def get_member_visits(
    db: psycopg.AsyncConnection,
    member_id: int,
    gym_id: int,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    offset = (page - 1) * limit
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT COUNT(*) AS total FROM gym_visits WHERE member_id = %s AND gym_id = %s",
            (member_id, gym_id),
        )
        total = (await cur.fetchone())["total"]

        await cur.execute(
            """
            SELECT * FROM gym_visits
            WHERE member_id = %s AND gym_id = %s
            ORDER BY check_in_time DESC
            LIMIT %s OFFSET %s
            """,
            (member_id, gym_id, limit, offset),
        )
        return await cur.fetchall(), total


async def get_today_checkins_count(db: psycopg.AsyncConnection, gym_id: int) -> int:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM gym_visits WHERE gym_id = %s AND visit_date = CURRENT_DATE",
            (gym_id,),
        )
        return (await cur.fetchone())["cnt"]
