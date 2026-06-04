import psycopg


async def get_chatbot_config(db: psycopg.AsyncConnection, gym_id: int) -> dict | None:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "SELECT * FROM gym_chatbot_config WHERE gym_id = %s",
            (gym_id,),
        )
        return await cur.fetchone()


async def upsert_chatbot_config(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO gym_chatbot_config (
                gym_id, bot_name, greeting_message, response_tone, bot_avatar_url,
                collect_leads, escalate_to_human,
                custom_faqs, knowledge_base, response_templates,
                supported_languages, can_book_demos, can_check_availability, can_share_pricing,
                primary_cta, secondary_cta, active_hours,
                conversation_timeout_minutes, is_active
            ) VALUES (
                %(gym_id)s, %(bot_name)s, %(greeting_message)s, %(response_tone)s, %(bot_avatar_url)s,
                %(collect_leads)s, %(escalate_to_human)s,
                %(custom_faqs)s, %(knowledge_base)s, %(response_templates)s,
                %(supported_languages)s, %(can_book_demos)s, %(can_check_availability)s, %(can_share_pricing)s,
                %(primary_cta)s, %(secondary_cta)s, %(active_hours)s,
                %(conversation_timeout_minutes)s, %(is_active)s
            )
            ON CONFLICT (gym_id) DO UPDATE SET
                bot_name = EXCLUDED.bot_name,
                greeting_message = EXCLUDED.greeting_message,
                response_tone = EXCLUDED.response_tone,
                bot_avatar_url = EXCLUDED.bot_avatar_url,
                collect_leads = EXCLUDED.collect_leads,
                escalate_to_human = EXCLUDED.escalate_to_human,
                custom_faqs = EXCLUDED.custom_faqs,
                knowledge_base = EXCLUDED.knowledge_base,
                response_templates = EXCLUDED.response_templates,
                supported_languages = EXCLUDED.supported_languages,
                can_book_demos = EXCLUDED.can_book_demos,
                can_check_availability = EXCLUDED.can_check_availability,
                can_share_pricing = EXCLUDED.can_share_pricing,
                primary_cta = EXCLUDED.primary_cta,
                secondary_cta = EXCLUDED.secondary_cta,
                active_hours = EXCLUDED.active_hours,
                conversation_timeout_minutes = EXCLUDED.conversation_timeout_minutes,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            RETURNING *
            """,
            {**data, "gym_id": gym_id},
        )
        return await cur.fetchone()


async def build_gym_knowledge_base(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    """Gather all gym data needed to power the chatbot context."""
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        # Gym basics
        await cur.execute(
            """
            SELECT gym_name, full_address, city, state, phone_number, whatsapp_number,
                   website, instagram_url, facebook_url, gym_type, amenities,
                   average_rating, total_reviews, parking_available
            FROM gyms WHERE id = %s
            """,
            (gym_id,),
        )
        gym = await cur.fetchone()

        # Operating hours
        await cur.execute(
            "SELECT day_of_week, is_open, opening_time, closing_time, is_24_hours FROM gym_operating_hours WHERE gym_id = %s ORDER BY day_of_week",
            (gym_id,),
        )
        hours = await cur.fetchall()

        # Active plans
        await cur.execute(
            "SELECT plan_name, duration_months, original_price, discounted_price, features, included_services, trial_available, trial_duration_days FROM gym_plans WHERE gym_id = %s AND is_active = TRUE ORDER BY original_price",
            (gym_id,),
        )
        plans = await cur.fetchall()

        # Facilities
        await cur.execute(
            "SELECT category, facility_name FROM gym_facilities WHERE gym_id = %s AND is_available = TRUE ORDER BY category",
            (gym_id,),
        )
        facilities = await cur.fetchall()

        # Chatbot config (custom FAQs, CTA)
        await cur.execute(
            "SELECT bot_name, greeting_message, response_tone, primary_cta, secondary_cta, custom_faqs, collect_leads FROM gym_chatbot_config WHERE gym_id = %s",
            (gym_id,),
        )
        config = await cur.fetchone()

        return {
            "gym": gym,
            "hours": hours,
            "plans": plans,
            "facilities": facilities,
            "chatbot_config": config,
        }
