"""Queries for gym_admins table — manages gym owner/manager/staff access."""
import psycopg


async def get_gym_access(db: psycopg.AsyncConnection, user_id: int, gym_id: int) -> dict | None:
    """Returns the gym_admins row if this user has any active role in this gym."""
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT ga.*, g.owner_user_id
            FROM gym_admins ga
            JOIN gyms g ON g.id = ga.gym_id
            WHERE ga.user_id = %s AND ga.gym_id = %s AND ga.is_active = TRUE
            """,
            (user_id, gym_id),
        )
        return await cur.fetchone()


async def get_gym_staff(db: psycopg.AsyncConnection, gym_id: int) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT ga.id, ga.role, ga.permissions, ga.access_level, ga.is_active,
                   ga.joining_date, ga.employment_type, ga.created_at,
                   u.id AS user_id, u.full_name, u.email, u.phone, u.profile_photo_url
            FROM gym_admins ga
            JOIN users u ON ga.user_id = u.id
            WHERE ga.gym_id = %s
            ORDER BY ga.access_level DESC, ga.created_at ASC
            """,
            (gym_id,),
        )
        return await cur.fetchall()


async def add_gym_staff(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO gym_admins (user_id, gym_id, role, permissions, access_level, invited_by, employment_type)
            VALUES (%(user_id)s, %(gym_id)s, %(role)s, %(permissions)s, %(access_level)s, %(invited_by)s, %(employment_type)s)
            ON CONFLICT (user_id, gym_id) DO UPDATE
                SET role = EXCLUDED.role,
                    permissions = EXCLUDED.permissions,
                    access_level = EXCLUDED.access_level,
                    is_active = TRUE,
                    updated_at = NOW()
            RETURNING *
            """,
            {**data, "gym_id": gym_id},
        )
        return await cur.fetchone()


async def remove_gym_staff(db: psycopg.AsyncConnection, gym_id: int, user_id: int) -> bool:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE gym_admins SET is_active = FALSE, updated_at = NOW() WHERE gym_id = %s AND user_id = %s",
            (gym_id, user_id),
        )
        return cur.rowcount > 0


async def update_staff_permissions(db: psycopg.AsyncConnection, gym_id: int, user_id: int, permissions: dict) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE gym_admins SET permissions = %s, updated_at = NOW()
            WHERE gym_id = %s AND user_id = %s AND is_active = TRUE
            RETURNING *
            """,
            (psycopg.types.json.Jsonb(permissions), gym_id, user_id),
        )
        return await cur.fetchone()


async def seed_owner_as_admin(db: psycopg.AsyncConnection, gym_id: int, owner_user_id: int) -> None:
    """Called when a gym is created — seeds the owner into gym_admins with full access."""
    async with db.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO gym_admins (user_id, gym_id, role, permissions, access_level, invited_by)
            VALUES (%s, %s, 'OWNER', '{"all": true}', 10, %s)
            ON CONFLICT (user_id, gym_id) DO NOTHING
            """,
            (owner_user_id, gym_id, owner_user_id),
        )
