import psycopg


async def create_review(db: psycopg.AsyncConnection, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO reviews (
                gym_id, reviewer_user_id, rating, review_title,
                review_content, review_type, reviewer_name, reviewer_email
            ) VALUES (
                %(gym_id)s, %(reviewer_user_id)s, %(rating)s, %(review_title)s,
                %(review_content)s, %(review_type)s, %(reviewer_name)s, %(reviewer_email)s
            )
            RETURNING *
            """,
            data,
        )
        return await cur.fetchone()


async def get_gym_reviews(
    db: psycopg.AsyncConnection,
    gym_id: int | None,
    status: str = "APPROVED",
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    offset = (page - 1) * limit
    # gym_id=None means all gyms (admin view)
    where_gym = "AND r.gym_id = %s" if gym_id else ""
    params_gym = (gym_id,) if gym_id else ()

    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"SELECT COUNT(*) AS total FROM reviews r WHERE r.status = %s {where_gym}",
            (status, *params_gym),
        )
        total = (await cur.fetchone())["total"]

        await cur.execute(
            f"""
            SELECT r.*, u.full_name AS user_name, g.gym_name
            FROM reviews r
            LEFT JOIN users u ON r.reviewer_user_id = u.id
            LEFT JOIN gyms g ON r.gym_id = g.id
            WHERE r.status = %s {where_gym}
            ORDER BY r.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (status, *params_gym, limit, offset),
        )
        return await cur.fetchall(), total


async def get_review_by_id(db: psycopg.AsyncConnection, review_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute("SELECT * FROM reviews WHERE id = %s", (review_id,))
        return await cur.fetchone()


async def respond_to_review(db: psycopg.AsyncConnection, review_id: int, response: str, responded_by: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE reviews
            SET response_content = %s, response_date = NOW(), responded_by = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (response, responded_by, review_id),
        )
        return await cur.fetchone()


async def moderate_review(db: psycopg.AsyncConnection, review_id: int, status: str, notes: str | None, moderated_by: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            UPDATE reviews
            SET status = %s, moderation_notes = %s, moderated_by = %s, moderated_at = NOW(), updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (status, notes, moderated_by, review_id),
        )
        return await cur.fetchone()


async def vote_review(db: psycopg.AsyncConnection, review_id: int, helpful: bool) -> dict:
    col = "helpful_votes" if helpful else "unhelpful_votes"
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"UPDATE reviews SET {col} = {col} + 1 WHERE id = %s RETURNING helpful_votes, unhelpful_votes",
            (review_id,),
        )
        return await cur.fetchone()


async def get_gym_rating_summary(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                COUNT(*) AS total_reviews,
                ROUND(AVG(rating)::NUMERIC, 1) AS average_rating,
                COUNT(*) FILTER (WHERE rating = 5) AS five_star,
                COUNT(*) FILTER (WHERE rating = 4) AS four_star,
                COUNT(*) FILTER (WHERE rating = 3) AS three_star,
                COUNT(*) FILTER (WHERE rating = 2) AS two_star,
                COUNT(*) FILTER (WHERE rating = 1) AS one_star
            FROM reviews
            WHERE gym_id = %s AND status = 'APPROVED'
            """,
            (gym_id,),
        )
        return await cur.fetchone()
