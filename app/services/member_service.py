import json
import logging
import psycopg

from app.core.exceptions import ForbiddenException, NotFoundException
from app.database.queries import gym_queries, member_queries, notification_queries
from app.database.queries import gym_admin_queries
from app.utils.pagination import paginated_response
from app.utils.whatsapp import send_bulk_whatsapp, new_lead_message, membership_expiry_message

logger = logging.getLogger(__name__)


async def _assert_gym_access(db: psycopg.AsyncConnection, gym: dict, user: dict) -> None:
    if user["role"] in ("SUPER_ADMIN", "ADMIN"):
        return
    access = await gym_admin_queries.get_gym_access(db, user["id"], gym["id"])
    if not access:
        raise ForbiddenException("You do not have access to this gym.")


async def add_member(db: psycopg.AsyncConnection, gym_id: int, requesting_user: dict, data: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await _assert_gym_access(db, gym, requesting_user)

    member_data = {
        **data,
        "address": json.dumps(data.get("address")) if data.get("address") else None,
        "fitness_goals": json.dumps(data.get("fitness_goals")) if data.get("fitness_goals") else None,
        "dietary_restrictions": data.get("dietary_restrictions", []),
        "interested_classes": data.get("interested_classes", []),
        "tags": data.get("tags", []),
    }
    member = await member_queries.add_member(db, gym_id, member_data)
    await db.commit()
    logger.info("Member added: %s to gym %s", data["member_name"], gym_id)
    return member


async def get_member(db: psycopg.AsyncConnection, gym_id: int, member_id: int, requesting_user: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await _assert_gym_access(db, gym, requesting_user)
    member = await member_queries.get_member_by_id(db, member_id, gym_id)
    if not member:
        raise NotFoundException("Member")
    return member


async def list_members(
    db: psycopg.AsyncConnection,
    gym_id: int,
    requesting_user: dict,
    search: str | None,
    status: str | None,
    page: int,
    limit: int,
) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await _assert_gym_access(db, gym, requesting_user)
    members, total = await member_queries.get_members(db, gym_id, search, status, limit, (page - 1) * limit)
    return paginated_response(members, total, page, limit)


async def update_member(db: psycopg.AsyncConnection, gym_id: int, member_id: int, requesting_user: dict, data: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await _assert_gym_access(db, gym, requesting_user)
    updated = await member_queries.update_member(db, member_id, gym_id, data)
    if not updated:
        raise NotFoundException("Member")
    await db.commit()
    return updated


async def add_membership(db: psycopg.AsyncConnection, gym_id: int, member_id: int, requesting_user: dict, data: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await _assert_gym_access(db, gym, requesting_user)

    member = await member_queries.get_member_by_id(db, member_id, gym_id)
    if not member:
        raise NotFoundException("Member")

    membership = await member_queries.add_membership(db, member_id, {**data, "created_by": requesting_user["id"]})
    # Activate the member status
    await member_queries.update_member_status(db, member_id, gym_id, "ACTIVE")
    await db.commit()
    return membership


async def get_dashboard_stats(db: psycopg.AsyncConnection, gym_id: int, requesting_user: dict) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await _assert_gym_access(db, gym, requesting_user)
    return await member_queries.get_member_dashboard_stats(db, gym_id)


async def send_bulk_message(
    db: psycopg.AsyncConnection,
    gym_id: int,
    requesting_user: dict,
    message: str,
    member_ids: list[int] | None,
) -> dict:
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await _assert_gym_access(db, gym, requesting_user)

    if member_ids:
        # Get only specific members' phones
        all_members = await member_queries.get_members_with_whatsapp_enabled(db, gym_id)
        targets = [m for m in all_members if m["id"] in member_ids]
    else:
        targets = await member_queries.get_members_with_whatsapp_enabled(db, gym_id)

    phones = [m["phone"] for m in targets if m.get("phone")]
    results = await send_bulk_whatsapp(phones, message)

    # Log communication
    await notification_queries.log_communication(db, {
        "gym_id": gym_id,
        "trainer_id": None,
        "recipient_type": "MEMBER",
        "recipient_id": None,
        "recipient_phone": None,
        "recipient_email": None,
        "recipient_name": f"Bulk ({len(phones)} members)",
        "communication_type": "WHATSAPP",
        "subject": "Bulk Message",
        "message_content": message,
        "status": "SENT",
        "purpose": "BULK_BROADCAST",
    })
    await db.commit()
    return results


async def send_expiry_reminders(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    """Called manually or via scheduled job to remind members expiring in 7 days."""
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")

    expiring = await member_queries.get_expiring_memberships(db, gym_id, days_ahead=7)
    sent = 0
    for member in expiring:
        days_left = (member["end_date"] - __import__("datetime").date.today()).days
        msg = membership_expiry_message(member["member_name"], gym["gym_name"], days_left)
        success = await __import__("app.utils.whatsapp", fromlist=["send_whatsapp"]).send_whatsapp(member["phone"], msg)
        if success:
            sent += 1
    return {"total_expiring": len(expiring), "reminders_sent": sent}
