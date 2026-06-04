import json
import logging
import psycopg

from app.core.exceptions import AlreadyExistsException, ForbiddenException, NotFoundException
from app.database.queries import gym_queries
from app.database.queries import gym_admin_queries
from app.utils.helpers import slugify
from app.utils.pagination import paginated_response

logger = logging.getLogger(__name__)


async def create_gym(db: psycopg.AsyncConnection, owner_user_id: int, data: dict) -> dict:
    base_slug = slugify(data["gym_name"])
    slug = base_slug
    counter = 1
    while await gym_queries.get_gym_by_slug(db, slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    gym_data = {
        **data,
        "slug": slug,
        "owner_user_id": owner_user_id,
        "subscription_tier": "FREE",
        "amenities": json.dumps(data.get("amenities") or {}),
    }
    gym = await gym_queries.create_gym(db, gym_data)
    # Seed owner into gym_admins for consistent access checks
    await gym_admin_queries.seed_owner_as_admin(db, gym["id"], owner_user_id)
    await db.commit()
    logger.info("Gym created: %s (id=%s) by user %s", data["gym_name"], gym["id"], owner_user_id)
    return gym


async def get_gym(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await gym_queries.increment_page_views(db, gym_id)
    await db.commit()
    return gym


async def get_gym_by_slug(db: psycopg.AsyncConnection, slug: str) -> dict:
    gym = await gym_queries.get_gym_by_slug(db, slug)
    if not gym:
        raise NotFoundException("Gym")
    await gym_queries.increment_page_views(db, gym["id"])
    await db.commit()
    return gym


async def list_gyms(
    db: psycopg.AsyncConnection,
    city: str | None,
    state: str | None,
    gym_type: str | None,
    search: str | None,
    page: int,
    limit: int,
) -> dict:
    gyms, total = await gym_queries.search_gyms(
        db, city=city, state=state, gym_type=gym_type, search=search,
        limit=limit, offset=(page - 1) * limit,
    )
    return paginated_response(gyms, total, page, limit)


async def update_gym(db: psycopg.AsyncConnection, gym_id: int, requesting_user: dict, data: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await assert_gym_access(db, gym, requesting_user)
    updated = await gym_queries.update_gym(db, gym_id, data)
    await db.commit()
    return updated


async def upload_gym_logo(db: psycopg.AsyncConnection, gym_id: int, requesting_user: dict, file_bytes: bytes, content_type: str) -> str:
    from app.utils.file_upload import upload_image
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await assert_gym_access(db, gym, requesting_user)
    result = await upload_image(file_bytes, content_type, folder=f"gyms/{gym_id}/logo", public_id="logo")
    await gym_queries.update_gym_logo(db, gym_id, result["url"])
    await db.commit()
    return result["url"]


async def approve_gym(db: psycopg.AsyncConnection, gym_id: int) -> None:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await gym_queries.approve_gym(db, gym_id)
    await db.commit()


# ─── Plans ────────────────────────────────────────────────────────────────────

async def create_plan(db: psycopg.AsyncConnection, gym_id: int, requesting_user: dict, data: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await assert_gym_access(db, gym, requesting_user)
    import json
    plan_data = {
        **data,
        "features": json.dumps(data.get("features", {})),
        "included_services": data.get("included_services", []),
    }
    plan = await gym_queries.create_gym_plan(db, gym_id, plan_data)
    await db.commit()
    return plan


async def get_plans(db: psycopg.AsyncConnection, gym_id: int, active_only: bool = True) -> list[dict]:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    return await gym_queries.get_gym_plans(db, gym_id, active_only)


async def update_plan(db: psycopg.AsyncConnection, gym_id: int, plan_id: int, requesting_user: dict, data: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await assert_gym_access(db, gym, requesting_user)
    plan = await gym_queries.update_gym_plan(db, plan_id, gym_id, data)
    if not plan:
        raise NotFoundException("Plan")
    await db.commit()
    return plan


async def delete_plan(db: psycopg.AsyncConnection, gym_id: int, plan_id: int, requesting_user: dict) -> None:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await assert_gym_access(db, gym, requesting_user)
    deleted = await gym_queries.delete_gym_plan(db, plan_id, gym_id)
    if not deleted:
        raise NotFoundException("Plan")
    await db.commit()


# ─── Operating Hours ──────────────────────────────────────────────────────────

async def set_operating_hours(db: psycopg.AsyncConnection, gym_id: int, requesting_user: dict, hours: list[dict]) -> None:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await assert_gym_access(db, gym, requesting_user)
    await gym_queries.upsert_operating_hours(db, gym_id, hours)
    await db.commit()


# ─── Internal Helper ─────────────────────────────────────────────────────────

async def assert_gym_access(db: psycopg.AsyncConnection, gym: dict, user: dict, require_owner: bool = False) -> None:
    """
    SUPER_ADMIN / ADMIN → always allowed.
    GYM_OWNER / GYM_MANAGER → must have an active row in gym_admins for this gym.
    require_owner=True → only OWNER role in gym_admins allowed (e.g. deleting gym, billing).
    """
    if user["role"] in ("SUPER_ADMIN", "ADMIN"):
        return
    access = await gym_admin_queries.get_gym_access(db, user["id"], gym["id"])
    if not access:
        raise ForbiddenException("You do not have access to this gym.")
    if require_owner and access["role"] != "OWNER":
        raise ForbiddenException("Only the gym owner can perform this action.")


def _assert_gym_access(gym: dict, user: dict) -> None:
    """Sync fallback — only use where DB is not available. Prefer assert_gym_access()."""
    if user["role"] in ("SUPER_ADMIN", "ADMIN"):
        return
    if gym["owner_user_id"] != user["id"]:
        raise ForbiddenException("You do not have access to this gym.")
