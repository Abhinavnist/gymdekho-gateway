from fastapi import APIRouter, Query
from app.core.dependencies import DBConn, CurrentUser
from app.models.member import MemberCreateRequest, MemberUpdateRequest, MemberStatusRequest, AddMembershipRequest, BulkWhatsAppRequest
from app.services import member_service
from app.utils.response import success_response

router = APIRouter(prefix="/gyms/{gym_id}/members", tags=["Members"])


@router.get("/")
async def list_members(
    gym_id: int,
    db: DBConn,
    current_user: CurrentUser,
    search: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    result = await member_service.list_members(db, gym_id, current_user, search, status, page, limit)
    return success_response(result)


@router.post("/", status_code=201)
async def add_member(gym_id: int, body: MemberCreateRequest, db: DBConn, current_user: CurrentUser):
    member = await member_service.add_member(db, gym_id, current_user, body.model_dump())
    return success_response(member, "Member added successfully.", 201)


@router.get("/stats")
async def member_stats(gym_id: int, db: DBConn, current_user: CurrentUser):
    stats = await member_service.get_dashboard_stats(db, gym_id, current_user)
    return success_response(stats)


@router.get("/{member_id}")
async def get_member(gym_id: int, member_id: int, db: DBConn, current_user: CurrentUser):
    member = await member_service.get_member(db, gym_id, member_id, current_user)
    return success_response(member)


@router.put("/{member_id}")
async def update_member(gym_id: int, member_id: int, body: MemberUpdateRequest, db: DBConn, current_user: CurrentUser):
    updated = await member_service.update_member(db, gym_id, member_id, current_user, body.model_dump(exclude_none=True))
    return success_response(updated)


@router.patch("/{member_id}/status")
async def update_member_status(gym_id: int, member_id: int, body: MemberStatusRequest, db: DBConn, current_user: CurrentUser):
    from app.database.queries import member_queries
    await member_queries.update_member_status(db, member_id, gym_id, body.status)
    await db.commit()
    return success_response(message="Status updated.")


@router.post("/{member_id}/memberships", status_code=201)
async def add_membership(gym_id: int, member_id: int, body: AddMembershipRequest, db: DBConn, current_user: CurrentUser):
    membership = await member_service.add_membership(db, gym_id, member_id, current_user, body.model_dump())
    return success_response(membership, "Membership added.", 201)


@router.post("/bulk-whatsapp")
async def bulk_whatsapp(gym_id: int, body: BulkWhatsAppRequest, db: DBConn, current_user: CurrentUser):
    result = await member_service.send_bulk_message(db, gym_id, current_user, body.message, body.member_ids)
    return success_response(result, "Messages dispatched.")


@router.post("/send-expiry-reminders")
async def send_expiry_reminders(gym_id: int, db: DBConn, current_user: CurrentUser):
    result = await member_service.send_expiry_reminders(db, gym_id)
    return success_response(result)
