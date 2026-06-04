from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from app.core.dependencies import DBConn, CurrentUser, require_roles
from app.database.queries import review_queries
from app.core.exceptions import NotFoundException, ForbiddenException
from app.utils.response import success_response
from app.utils.pagination import paginated_response
from fastapi import Depends

router = APIRouter(tags=["Reviews"])


class ReviewCreateRequest(BaseModel):
    gym_id: int
    rating: int = Field(..., ge=1, le=5)
    review_title: str | None = None
    review_content: str | None = None
    review_type: str = "GENERAL"
    reviewer_name: str | None = None
    reviewer_email: str | None = None


class ReviewRespondRequest(BaseModel):
    response_content: str = Field(..., min_length=1)


class ReviewModerateRequest(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED|HIDDEN)$")
    moderation_notes: str | None = None


# ─── Public ───────────────────────────────────────────────────────────────────

@router.get("/gyms/{gym_id}/reviews")
async def list_reviews(
    gym_id: int,
    db: DBConn,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    rows, total = await review_queries.get_gym_reviews(db, gym_id, status="APPROVED", page=page, limit=limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.get("/gyms/{gym_id}/reviews/summary")
async def review_summary(gym_id: int, db: DBConn):
    summary = await review_queries.get_gym_rating_summary(db, gym_id)
    return success_response(summary)


@router.post("/gyms/{gym_id}/reviews/vote/{review_id}")
async def vote(gym_id: int, review_id: int, helpful: bool, db: DBConn):
    result = await review_queries.vote_review(db, review_id, helpful)
    await db.commit()
    return success_response(result)


# ─── Authenticated ────────────────────────────────────────────────────────────

@router.post("/reviews", status_code=201)
async def create_review(body: ReviewCreateRequest, db: DBConn, current_user: CurrentUser):
    data = body.model_dump()
    data["reviewer_user_id"] = current_user["id"]
    if not data.get("reviewer_name"):
        data["reviewer_name"] = current_user.get("full_name")
    if not data.get("reviewer_email"):
        data["reviewer_email"] = current_user.get("email")
    review = await review_queries.create_review(db, data)
    await db.commit()
    return success_response(review, "Review submitted. Pending moderation.", 201)


@router.post("/reviews/{review_id}/respond")
async def respond(review_id: int, body: ReviewRespondRequest, db: DBConn, current_user: CurrentUser):
    review = await review_queries.get_review_by_id(db, review_id)
    if not review:
        raise NotFoundException("Review")
    updated = await review_queries.respond_to_review(db, review_id, body.response_content, current_user["id"])
    await db.commit()
    return success_response(updated)


# ─── Admin moderation ─────────────────────────────────────────────────────────

@router.get("/admin/reviews", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def list_all_reviews(
    db: DBConn,
    current_user: CurrentUser,
    gym_id: int | None = Query(None),
    status: str = Query("PENDING"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    # gym_id=None → all gyms (admin can see all reviews platform-wide)
    rows, total = await review_queries.get_gym_reviews(db, gym_id, status=status, page=page, limit=limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.patch("/admin/reviews/{review_id}/moderate", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def moderate(
    review_id: int,
    body: ReviewModerateRequest,
    db: DBConn,
    current_user: CurrentUser,
):
    review = await review_queries.get_review_by_id(db, review_id)
    if not review:
        raise NotFoundException("Review")
    updated = await review_queries.moderate_review(db, review_id, body.status, body.moderation_notes, current_user["id"])
    await db.commit()
    return success_response(updated)
