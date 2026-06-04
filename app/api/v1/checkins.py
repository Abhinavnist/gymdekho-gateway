from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.core.dependencies import DBConn, CurrentUser
from app.database.queries import checkin_queries
from app.database.queries import member_queries
from app.core.exceptions import NotFoundException, ValidationException
from app.utils.response import success_response
from app.utils.pagination import paginated_response
import json

router = APIRouter(tags=["Check-ins"])


class CheckInRequest(BaseModel):
    member_id: int
    gym_id: int
    visit_type: str = "REGULAR"
    purpose: str | None = None
    entry_method: str = "MANUAL"
    facilities_used: list[str] | None = None


class CheckOutRequest(BaseModel):
    visit_id: int
    gym_id: int


@router.post("/checkins", status_code=201)
async def check_in(body: CheckInRequest, db: DBConn, current_user: CurrentUser):
    # Ensure member belongs to this gym
    member = await member_queries.get_member_by_id(db, body.member_id, body.gym_id)
    if not member:
        raise NotFoundException("Member")

    # Prevent double check-in
    active = await checkin_queries.get_active_visit(db, body.member_id, body.gym_id)
    if active:
        raise ValidationException("Member is already checked in.")

    data = {
        "member_id": body.member_id,
        "gym_id": body.gym_id,
        "visit_type": body.visit_type,
        "purpose": body.purpose,
        "entry_method": body.entry_method,
        "facilities_used": json.dumps(body.facilities_used or []),
    }
    visit = await checkin_queries.check_in(db, data)
    await db.commit()
    return success_response(visit, "Checked in successfully.", 201)


@router.post("/checkins/checkout")
async def check_out(body: CheckOutRequest, db: DBConn, current_user: CurrentUser):
    visit = await checkin_queries.check_out(db, body.visit_id, body.gym_id)
    if not visit:
        raise NotFoundException("Active check-in")
    await db.commit()
    return success_response(visit, "Checked out successfully.")


@router.get("/gyms/{gym_id}/checkins")
async def gym_checkins(
    gym_id: int,
    db: DBConn,
    current_user: CurrentUser,
    date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    rows, total = await checkin_queries.get_gym_visits(db, gym_id, date_filter=date, page=page, limit=limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.get("/gyms/{gym_id}/checkins/today-count")
async def today_count(gym_id: int, db: DBConn, current_user: CurrentUser):
    count = await checkin_queries.get_today_checkins_count(db, gym_id)
    return success_response({"today_checkins": count})


@router.get("/gyms/{gym_id}/members/{member_id}/visits")
async def member_visits(
    gym_id: int,
    member_id: int,
    db: DBConn,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    rows, total = await checkin_queries.get_member_visits(db, member_id, gym_id, page, limit)
    return success_response(paginated_response(rows, total, page, limit))
