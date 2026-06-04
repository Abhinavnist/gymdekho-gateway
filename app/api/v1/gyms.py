import json
from fastapi import APIRouter, Query, UploadFile, File, Depends
from pydantic import BaseModel

from app.core.dependencies import DBConn, CurrentUser, require_roles
from app.models.gym import (
    GymCreateRequest, GymUpdateRequest,
    GymPlanCreateRequest, GymPlanUpdateRequest,
    OperatingHoursRequest, FacilityCreateRequest,
)
from app.services import gym_service
from app.database.queries import gym_queries, analytics_queries, gym_admin_queries, user_queries
from app.core.exceptions import NotFoundException
from app.utils.response import success_response


def _json(data: dict) -> str:
    return json.dumps(data)


class AddStaffRequest(BaseModel):
    email: str
    role: str = "GYM_MANAGER"
    employment_type: str | None = None


class UpdatePermissionsRequest(BaseModel):
    permissions: dict


router = APIRouter(prefix="/gyms", tags=["Gyms"])


# ─── IMPORTANT: Static paths MUST come before /{gym_id} ──────────────────────

# ─── Public ───────────────────────────────────────────────────────────────────

@router.get("/")
async def list_gyms(
    db: DBConn,
    city: str | None = Query(None),
    state: str | None = Query(None),
    gym_type: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    result = await gym_service.list_gyms(db, city, state, gym_type, search, page, limit)
    return success_response(result)


@router.get("/my")
async def my_gyms(db: DBConn, current_user: CurrentUser):
    """Returns all gyms owned/managed by the logged-in user."""
    gyms = await gym_queries.get_gym_by_owner(db, current_user["id"])
    return success_response(gyms)


@router.get("/slug/{slug}")
async def get_gym_by_slug(slug: str, db: DBConn):
    gym = await gym_service.get_gym_by_slug(db, slug)
    return success_response(gym)


@router.post("/", status_code=201)
async def create_gym(body: GymCreateRequest, db: DBConn, current_user: CurrentUser):
    gym = await gym_service.create_gym(db, current_user["id"], body.model_dump())
    return success_response(gym, "Gym registered successfully. Pending admin approval.", 201)


# ─── Dynamic /{gym_id} routes (MUST be after all static routes) ───────────────

@router.get("/{gym_id}")
async def get_gym(gym_id: int, db: DBConn):
    gym = await gym_service.get_gym(db, gym_id)
    return success_response(gym)


@router.put("/{gym_id}")
async def update_gym(gym_id: int, body: GymUpdateRequest, db: DBConn, current_user: CurrentUser):
    updated = await gym_service.update_gym(db, gym_id, current_user, body.model_dump(exclude_none=True))
    return success_response(updated)


@router.post("/{gym_id}/logo")
async def upload_logo(gym_id: int, db: DBConn, current_user: CurrentUser, file: UploadFile = File(...)):
    content = await file.read()
    url = await gym_service.upload_gym_logo(db, gym_id, current_user, content, file.content_type)
    return success_response({"logo_url": url})


# ─── Public sub-routes ────────────────────────────────────────────────────────

@router.get("/{gym_id}/plans")
async def get_gym_plans(gym_id: int, db: DBConn):
    plans = await gym_service.get_plans(db, gym_id, active_only=True)
    return success_response(plans)


@router.get("/{gym_id}/hours")
async def get_operating_hours(gym_id: int, db: DBConn):
    hours = await gym_queries.get_operating_hours(db, gym_id)
    return success_response(hours)


@router.get("/{gym_id}/facilities")
async def get_facilities(gym_id: int, db: DBConn):
    facilities = await gym_queries.get_facilities(db, gym_id)
    return success_response(facilities)


@router.get("/{gym_id}/reviews")
async def gym_reviews(
    gym_id: int, db: DBConn,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    from app.database.queries import review_queries
    from app.utils.pagination import paginated_response
    rows, total = await review_queries.get_gym_reviews(db, gym_id, status="APPROVED", page=page, limit=limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.get("/{gym_id}/reviews/summary")
async def gym_review_summary(gym_id: int, db: DBConn):
    from app.database.queries import review_queries
    summary = await review_queries.get_gym_rating_summary(db, gym_id)
    return success_response(summary)


@router.post("/{gym_id}/reviews/vote/{review_id}")
async def vote_review(gym_id: int, review_id: int, helpful: bool, db: DBConn):
    from app.database.queries import review_queries
    result = await review_queries.vote_review(db, review_id, helpful)
    await db.commit()
    return success_response(result)


# ─── Authenticated (Gym Owner / Manager) ─────────────────────────────────────

@router.get("/{gym_id}/dashboard")
async def gym_dashboard(gym_id: int, db: DBConn, current_user: CurrentUser):
    stats = await analytics_queries.get_gym_dashboard_stats(db, gym_id)
    return success_response(stats)


@router.get("/{gym_id}/analytics/growth")
async def member_growth(gym_id: int, db: DBConn, current_user: CurrentUser, months: int = Query(6, ge=1, le=12)):
    data = await analytics_queries.get_monthly_member_growth(db, gym_id, months)
    return success_response(data)


@router.get("/{gym_id}/analytics/revenue")
async def revenue_summary(gym_id: int, db: DBConn, current_user: CurrentUser, months: int = Query(3, ge=1, le=12)):
    data = await analytics_queries.get_revenue_summary(db, gym_id, months)
    return success_response(data)


@router.get("/{gym_id}/analytics/funnel")
async def lead_funnel(gym_id: int, db: DBConn, current_user: CurrentUser):
    data = await analytics_queries.get_lead_funnel(db, gym_id)
    return success_response(data)


@router.get("/{gym_id}/subscription")
async def gym_subscription(gym_id: int, db: DBConn, current_user: CurrentUser):
    from app.database.queries.subscription_queries import get_gym_active_subscription
    sub = await get_gym_active_subscription(db, gym_id)
    return success_response(sub)


# ─── Plans ────────────────────────────────────────────────────────────────────

@router.post("/{gym_id}/plans", status_code=201)
async def create_plan(gym_id: int, body: GymPlanCreateRequest, db: DBConn, current_user: CurrentUser):
    plan = await gym_service.create_plan(db, gym_id, current_user, body.model_dump())
    return success_response(plan, "Plan created.", 201)


@router.put("/{gym_id}/plans/{plan_id}")
async def update_plan(gym_id: int, plan_id: int, body: GymPlanUpdateRequest, db: DBConn, current_user: CurrentUser):
    plan = await gym_service.update_plan(db, gym_id, plan_id, current_user, body.model_dump(exclude_none=True))
    return success_response(plan)


@router.delete("/{gym_id}/plans/{plan_id}", status_code=204)
async def delete_plan(gym_id: int, plan_id: int, db: DBConn, current_user: CurrentUser):
    await gym_service.delete_plan(db, gym_id, plan_id, current_user)


# ─── Operating Hours ──────────────────────────────────────────────────────────

@router.post("/{gym_id}/hours")
async def set_hours(gym_id: int, body: OperatingHoursRequest, db: DBConn, current_user: CurrentUser):
    await gym_service.set_operating_hours(db, gym_id, current_user, [h.model_dump() for h in body.hours])
    return success_response(message="Operating hours updated.")


# ─── Facilities ───────────────────────────────────────────────────────────────

@router.post("/{gym_id}/facilities", status_code=201)
async def add_facility(gym_id: int, body: FacilityCreateRequest, db: DBConn, current_user: CurrentUser):
    facility = await gym_queries.add_facility(db, gym_id, body.model_dump())
    await db.commit()
    return success_response(facility, "Facility added.", 201)


@router.delete("/{gym_id}/facilities/{facility_id}", status_code=204)
async def delete_facility(gym_id: int, facility_id: int, db: DBConn, current_user: CurrentUser):
    await gym_queries.delete_facility(db, facility_id, gym_id)
    await db.commit()


# ─── Staff / Manager Management ───────────────────────────────────────────────

@router.get("/{gym_id}/staff")
async def list_staff(gym_id: int, db: DBConn, current_user: CurrentUser):
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await gym_service.assert_gym_access(db, gym, current_user)
    staff = await gym_admin_queries.get_gym_staff(db, gym_id)
    return success_response(staff)


@router.post("/{gym_id}/staff", status_code=201)
async def add_staff(gym_id: int, body: AddStaffRequest, db: DBConn, current_user: CurrentUser):
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await gym_service.assert_gym_access(db, gym, current_user, require_owner=True)

    user = await user_queries.get_user_by_email(db, body.email)
    if not user:
        raise NotFoundException(f"No user with email {body.email}. Ask them to register first.")

    permissions = {
        "view_members": True, "manage_members": True,
        "view_leads": True, "manage_leads": True,
        "view_analytics": body.role == "GYM_MANAGER",
        "manage_billing": False, "manage_staff": False,
    }
    record = await gym_admin_queries.add_gym_staff(db, gym_id, {
        "user_id": user["id"],
        "role": body.role,
        "permissions": _json(permissions),
        "access_level": 5 if body.role == "GYM_MANAGER" else 3,
        "invited_by": current_user["id"],
        "employment_type": body.employment_type,
    })
    await db.commit()
    return success_response(record, f"{body.role} added to gym.", 201)


@router.delete("/{gym_id}/staff/{user_id}", status_code=204)
async def remove_staff(gym_id: int, user_id: int, db: DBConn, current_user: CurrentUser):
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await gym_service.assert_gym_access(db, gym, current_user, require_owner=True)
    await gym_admin_queries.remove_gym_staff(db, gym_id, user_id)
    await db.commit()


@router.patch("/{gym_id}/staff/{user_id}/permissions")
async def update_permissions(gym_id: int, user_id: int, body: UpdatePermissionsRequest, db: DBConn, current_user: CurrentUser):
    gym = await gym_queries.get_gym_by_id(db, gym_id)
    if not gym:
        raise NotFoundException("Gym")
    await gym_service.assert_gym_access(db, gym, current_user, require_owner=True)
    updated = await gym_admin_queries.update_staff_permissions(db, gym_id, user_id, body.permissions)
    await db.commit()
    return success_response(updated)


# ─── Admin Only ───────────────────────────────────────────────────────────────

@router.get("/{gym_id}/checkins")
async def gym_checkins(
    gym_id: int, db: DBConn, current_user: CurrentUser,
    date: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    from app.database.queries import checkin_queries
    from app.utils.pagination import paginated_response
    rows, total = await checkin_queries.get_gym_visits(db, gym_id, date_filter=date, page=page, limit=limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.get("/{gym_id}/checkins/today-count")
async def today_count(gym_id: int, db: DBConn, current_user: CurrentUser):
    from app.database.queries import checkin_queries
    count = await checkin_queries.get_today_checkins_count(db, gym_id)
    return success_response({"today_checkins": count})


@router.get("/{gym_id}/members/{member_id}/visits")
async def member_visits(
    gym_id: int, member_id: int, db: DBConn, current_user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    from app.database.queries import checkin_queries
    from app.utils.pagination import paginated_response
    rows, total = await checkin_queries.get_member_visits(db, member_id, gym_id, page, limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.post("/{gym_id}/approve", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def approve_gym(gym_id: int, db: DBConn):
    await gym_service.approve_gym(db, gym_id)
    return success_response(message="Gym approved.")
