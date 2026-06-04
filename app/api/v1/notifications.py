from fastapi import APIRouter, Query
from app.core.dependencies import DBConn, CurrentUser
from app.database.queries import notification_queries
from app.utils.response import success_response
from app.utils.pagination import paginated_response

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/")
async def list_notifications(
    db: DBConn,
    current_user: CurrentUser,
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    rows, total = await notification_queries.get_user_notifications(
        db, current_user["id"], unread_only=unread_only, limit=limit, offset=(page - 1) * limit
    )
    return success_response(paginated_response(rows, total, page, limit))


@router.post("/mark-read")
async def mark_read(
    db: DBConn,
    current_user: CurrentUser,
    notification_ids: list[int] | None = None,
):
    """Pass notification_ids to mark specific ones, or omit to mark all."""
    await notification_queries.mark_notifications_read(db, current_user["id"], notification_ids)
    await db.commit()
    return success_response(message="Notifications marked as read.")


@router.get("/unread-count")
async def unread_count(db: DBConn, current_user: CurrentUser):
    _, total = await notification_queries.get_user_notifications(
        db, current_user["id"], unread_only=True, limit=1, offset=0
    )
    return success_response({"unread_count": total})
