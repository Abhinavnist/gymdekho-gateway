import psycopg
import json


async def create_gym(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO gyms (
                gym_name, slug, owner_user_id, owner_name, business_email,
                phone_number, whatsapp_number, full_address, city, state,
                country, zipcode, latitude, longitude, gym_type,
                establishment_year, total_area_sqft, max_capacity,
                website, instagram_url, facebook_url,
                amenities, subscription_tier
            ) VALUES (
                %(gym_name)s, %(slug)s, %(owner_user_id)s, %(owner_name)s, %(business_email)s,
                %(phone_number)s, %(whatsapp_number)s, %(full_address)s, %(city)s, %(state)s,
                %(country)s, %(zipcode)s, %(latitude)s, %(longitude)s, %(gym_type)s,
                %(establishment_year)s, %(total_area_sqft)s, %(max_capacity)s,
                %(website)s, %(instagram_url)s, %(facebook_url)s,
                %(amenities)s, %(subscription_tier)s
            )
            RETURNING id, gym_name, slug, approval_status, created_at
            """,
            data,
        )
        return await cur.fetchone()


async def get_gym_by_id(db: psycopg.AsyncConnection, gym_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT g.*,
                   u.full_name AS owner_full_name,
                   u.email AS owner_email
            FROM gyms g
            LEFT JOIN users u ON g.owner_user_id = u.id
            WHERE g.id = %s
            """,
            (gym_id,),
        )
        return await cur.fetchone()


async def get_gym_by_slug(db: psycopg.AsyncConnection, slug: str) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT * FROM gyms WHERE slug = %s AND is_active = TRUE",
            (slug,),
        )
        return await cur.fetchone()


async def get_gym_by_owner(db: psycopg.AsyncConnection, owner_user_id: int) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT id, gym_name, slug, city, state, is_active, is_verified,
                   approval_status, subscription_tier, average_rating, total_members, created_at
            FROM gyms
            WHERE owner_user_id = %s
            ORDER BY created_at DESC
            """,
            (owner_user_id,),
        )
        return await cur.fetchall()


async def search_gyms(
    db: psycopg.AsyncConnection,
    city: str | None = None,
    state: str | None = None,
    gym_type: str | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    conditions = ["g.is_active = TRUE", "g.approval_status = 'APPROVED'"]
    params: list = []

    if city:
        conditions.append("LOWER(g.city) = LOWER(%s)")
        params.append(city)
    if state:
        conditions.append("LOWER(g.state) = LOWER(%s)")
        params.append(state)
    if gym_type:
        conditions.append("g.gym_type = %s")
        params.append(gym_type)
    if search:
        conditions.append(
            "to_tsvector('english', g.gym_name || ' ' || COALESCE(g.meta_description, '')) @@ plainto_tsquery('english', %s)"
        )
        params.append(search)

    where = " AND ".join(conditions)

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM gyms g
            WHERE {where}
            """,
            params,
        )
        total_row = await cur.fetchone()
        total = total_row["total"]

        await cur.execute(
            f"""
            SELECT g.id, g.gym_name, g.slug, g.city, g.state, g.full_address,
                   g.logo_url, g.gym_type, g.average_rating, g.total_reviews,
                   g.total_members, g.featured_listing, g.subscription_tier
            FROM gyms g
            WHERE {where}
            ORDER BY g.featured_listing DESC, g.average_rating DESC
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        )
        rows = await cur.fetchall()
        return rows, total


async def update_gym(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE gyms SET
                gym_name = COALESCE(%(gym_name)s, gym_name),
                phone_number = COALESCE(%(phone_number)s, phone_number),
                whatsapp_number = COALESCE(%(whatsapp_number)s, whatsapp_number),
                full_address = COALESCE(%(full_address)s, full_address),
                city = COALESCE(%(city)s, city),
                state = COALESCE(%(state)s, state),
                zipcode = COALESCE(%(zipcode)s, zipcode),
                latitude = COALESCE(%(latitude)s, latitude),
                longitude = COALESCE(%(longitude)s, longitude),
                website = COALESCE(%(website)s, website),
                instagram_url = COALESCE(%(instagram_url)s, instagram_url),
                facebook_url = COALESCE(%(facebook_url)s, facebook_url),
                gym_type = COALESCE(%(gym_type)s, gym_type),
                amenities = COALESCE(%(amenities)s, amenities),
                meta_title = COALESCE(%(meta_title)s, meta_title),
                meta_description = COALESCE(%(meta_description)s, meta_description),
                updated_at = NOW()
            WHERE id = %(gym_id)s
            RETURNING id, gym_name, slug, city, updated_at
            """,
            {**data, "gym_id": gym_id},
        )
        return await cur.fetchone()


async def update_gym_logo(db: psycopg.AsyncConnection, gym_id: int, logo_url: str) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE gyms SET logo_url = %s, updated_at = NOW() WHERE id = %s",
            (logo_url, gym_id),
        )


async def update_gym_status(db: psycopg.AsyncConnection, gym_id: int, is_active: bool) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE gyms SET is_active = %s, updated_at = NOW() WHERE id = %s",
            (is_active, gym_id),
        )


async def approve_gym(db: psycopg.AsyncConnection, gym_id: int) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE gyms SET approval_status = 'APPROVED', is_verified = TRUE, updated_at = NOW() WHERE id = %s",
            (gym_id,),
        )


async def reject_gym(db: psycopg.AsyncConnection, gym_id: int, reason: str) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE gyms SET approval_status = 'REJECTED', updated_at = NOW() WHERE id = %s",
            (gym_id,),
        )


async def increment_page_views(db: psycopg.AsyncConnection, gym_id: int) -> None:
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE gyms SET page_views_count = page_views_count + 1 WHERE id = %s",
            (gym_id,),
        )


# ─── Plans ────────────────────────────────────────────────────────────────────

async def create_gym_plan(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO gym_plans (
                gym_id, plan_name, duration_months, original_price, discounted_price,
                registration_fee, features, included_services, trainer_sessions_included,
                trial_available, trial_duration_days, trial_cost, is_active, plan_category
            ) VALUES (
                %(gym_id)s, %(plan_name)s, %(duration_months)s, %(original_price)s, %(discounted_price)s,
                %(registration_fee)s, %(features)s, %(included_services)s, %(trainer_sessions_included)s,
                %(trial_available)s, %(trial_duration_days)s, %(trial_cost)s, %(is_active)s, %(plan_category)s
            )
            RETURNING *
            """,
            {**data, "gym_id": gym_id},
        )
        return await cur.fetchone()


async def get_gym_plans(db: psycopg.AsyncConnection, gym_id: int, active_only: bool = True) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        condition = "AND is_active = TRUE" if active_only else ""
        await cur.execute(
            f"SELECT * FROM gym_plans WHERE gym_id = %s {condition} ORDER BY original_price ASC",
            (gym_id,),
        )
        return await cur.fetchall()


async def update_gym_plan(db: psycopg.AsyncConnection, plan_id: int, gym_id: int, data: dict) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE gym_plans SET
                plan_name = COALESCE(%(plan_name)s, plan_name),
                duration_months = COALESCE(%(duration_months)s, duration_months),
                original_price = COALESCE(%(original_price)s, original_price),
                discounted_price = %(discounted_price)s,
                features = COALESCE(%(features)s, features),
                is_active = COALESCE(%(is_active)s, is_active),
                updated_at = NOW()
            WHERE id = %(plan_id)s AND gym_id = %(gym_id)s
            RETURNING *
            """,
            {**data, "plan_id": plan_id, "gym_id": gym_id},
        )
        return await cur.fetchone()


async def delete_gym_plan(db: psycopg.AsyncConnection, plan_id: int, gym_id: int) -> bool:
    async with db.cursor() as cur:
        await cur.execute(
            "DELETE FROM gym_plans WHERE id = %s AND gym_id = %s",
            (plan_id, gym_id),
        )
        return cur.rowcount > 0


# ─── Operating Hours ──────────────────────────────────────────────────────────

async def upsert_operating_hours(db: psycopg.AsyncConnection, gym_id: int, hours: list[dict]) -> None:
    async with db.cursor() as cur:
        await cur.execute("DELETE FROM gym_operating_hours WHERE gym_id = %s", (gym_id,))
        for h in hours:
            await cur.execute(
                """
                INSERT INTO gym_operating_hours (gym_id, day_of_week, is_open, opening_time, closing_time, is_24_hours)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (gym_id, h["day_of_week"], h["is_open"], h.get("opening_time"), h.get("closing_time"), h.get("is_24_hours", False)),
            )


async def get_operating_hours(db: psycopg.AsyncConnection, gym_id: int) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT * FROM gym_operating_hours WHERE gym_id = %s ORDER BY day_of_week",
            (gym_id,),
        )
        return await cur.fetchall()


# ─── Facilities ───────────────────────────────────────────────────────────────

async def add_facility(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO gym_facilities (gym_id, category, facility_name, description, quantity, is_available, is_premium)
            VALUES (%(gym_id)s, %(category)s, %(facility_name)s, %(description)s, %(quantity)s, %(is_available)s, %(is_premium)s)
            RETURNING *
            """,
            {**data, "gym_id": gym_id},
        )
        return await cur.fetchone()


async def get_facilities(db: psycopg.AsyncConnection, gym_id: int) -> list[dict]:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT * FROM gym_facilities WHERE gym_id = %s ORDER BY category, facility_name",
            (gym_id,),
        )
        return await cur.fetchall()


async def delete_facility(db: psycopg.AsyncConnection, facility_id: int, gym_id: int) -> bool:
    async with db.cursor() as cur:
        await cur.execute(
            "DELETE FROM gym_facilities WHERE id = %s AND gym_id = %s",
            (facility_id, gym_id),
        )
        return cur.rowcount > 0
