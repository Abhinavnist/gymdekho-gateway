from fastapi import APIRouter, Query
from app.core.dependencies import DBConn, CurrentUser
from app.models.lead import LeadUpdateRequest, LeadInteractionRequest
from app.database.queries import lead_queries
from app.utils.pagination import paginated_response
from app.utils.response import success_response

router = APIRouter(prefix="/gyms/{gym_id}/leads", tags=["Leads"])


@router.get("/")
async def list_leads(
    gym_id: int,
    db: DBConn,
    current_user: CurrentUser,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    leads, total = await lead_queries.get_leads(db, gym_id, status, search, priority, limit, (page - 1) * limit)
    return success_response(paginated_response(leads, total, page, limit))


@router.get("/stats")
async def lead_stats(gym_id: int, db: DBConn, current_user: CurrentUser):
    stats = await lead_queries.get_leads_dashboard_stats(db, gym_id)
    return success_response(stats)


@router.get("/{lead_id}")
async def get_lead(gym_id: int, lead_id: int, db: DBConn, current_user: CurrentUser):
    lead = await lead_queries.get_lead_by_id(db, lead_id, gym_id)
    if not lead:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Lead")
    return success_response(lead)


@router.patch("/{lead_id}")
async def update_lead(gym_id: int, lead_id: int, body: LeadUpdateRequest, db: DBConn, current_user: CurrentUser):
    updated = await lead_queries.update_lead(db, lead_id, gym_id, body.model_dump(exclude_none=True))
    await db.commit()
    return success_response(updated)


@router.patch("/{lead_id}/status")
async def update_lead_status(gym_id: int, lead_id: int, status: str, db: DBConn, current_user: CurrentUser):
    await lead_queries.update_lead_status(db, lead_id, gym_id, status)
    await db.commit()
    return success_response(message="Status updated.")


@router.get("/{lead_id}/interactions")
async def get_interactions(gym_id: int, lead_id: int, db: DBConn, current_user: CurrentUser):
    interactions = await lead_queries.get_lead_interactions(db, lead_id)
    return success_response(interactions)


@router.post("/{lead_id}/interactions", status_code=201)
async def add_interaction(gym_id: int, lead_id: int, body: LeadInteractionRequest, db: DBConn, current_user: CurrentUser):
    interaction = await lead_queries.add_lead_interaction(db, lead_id, {
        **body.model_dump(),
        "user_id": current_user["id"],
    })
    await db.commit()
    return success_response(interaction, "Interaction logged.", 201)


@router.post("/{lead_id}/convert")
async def convert_lead(gym_id: int, lead_id: int, member_id: int, db: DBConn, current_user: CurrentUser):
    await lead_queries.convert_lead_to_member(db, lead_id, gym_id, member_id)
    await db.commit()
    return success_response(message="Lead converted to member.")
