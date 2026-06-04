import secrets
from datetime import date, timedelta
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.core.dependencies import DBConn, CurrentUser, require_roles
from app.database.queries.subscription_queries import get_all_plans, get_gym_active_subscription
from app.database.queries.subscription_queries_ext import (
    get_plan_by_id, get_subscription_by_id, create_subscription,
    cancel_subscription, get_payment_history, create_payment_transaction,
)
from app.core.exceptions import NotFoundException, ValidationException
from app.utils.response import success_response
from app.utils.pagination import paginated_response
from fastapi import Depends

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


class SubscribeRequest(BaseModel):
    plan_id: int
    gym_id: int | None = None
    payment_method: str = "RAZORPAY"
    razorpay_payment_id: str | None = None


class CancelRequest(BaseModel):
    reason: str | None = None


# ─── Plans (public) ───────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(db: DBConn, target_type: str = Query("GYM", pattern="^(GYM|TRAINER|BOTH)$")):
    plans = await get_all_plans(db, target_type)
    return success_response(plans)


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: int, db: DBConn):
    plan = await get_plan_by_id(db, plan_id)
    if not plan:
        raise NotFoundException("Plan")
    return success_response(plan)


# ─── Current user subscription ────────────────────────────────────────────────

@router.get("/my")
async def my_subscription(db: DBConn, current_user: CurrentUser, gym_id: int | None = Query(None)):
    if gym_id:
        sub = await get_gym_active_subscription(db, gym_id)
    else:
        sub = None
    return success_response(sub)


@router.get("/my/payments")
async def payment_history(
    db: DBConn,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    rows, total = await get_payment_history(db, current_user["id"], page, limit)
    return success_response(paginated_response(rows, total, page, limit))


# ─── Subscribe / upgrade ──────────────────────────────────────────────────────

@router.post("/subscribe", status_code=201)
async def subscribe(body: SubscribeRequest, db: DBConn, current_user: CurrentUser):
    plan = await get_plan_by_id(db, body.plan_id)
    if not plan:
        raise NotFoundException("Plan")

    today = date.today()
    billing_months = plan.get("billing_cycle_months") or 1
    period_end = today + timedelta(days=billing_months * 30)

    sub_data = {
        "user_id": current_user["id"],
        "gym_id": body.gym_id,
        "plan_id": body.plan_id,
        "subscription_code": f"SUB-{secrets.token_hex(6).upper()}",
        "status": "TRIAL" if plan.get("trial_duration_days") else "ACTIVE",
        "current_period_start": today,
        "current_period_end": period_end,
        "amount_per_cycle": plan["base_price"],
        "total_amount": plan["base_price"],
        "auto_renewal": True,
        "next_billing_date": period_end,
    }
    sub = await create_subscription(db, sub_data)

    # Record payment transaction if paid plan
    if float(plan["base_price"]) > 0 and body.razorpay_payment_id:
        await create_payment_transaction(db, {
            "user_id": current_user["id"],
            "subscription_id": sub["id"],
            "transaction_id": f"TXN-{secrets.token_hex(8).upper()}",
            "transaction_type": "SUBSCRIPTION",
            "amount": plan["base_price"],
            "currency": "INR",
            "base_amount": plan["base_price"],
            "payment_method": body.payment_method,
            "payment_gateway": "RAZORPAY",
            "status": "SUCCESS",
            "payment_date": today,
            "description": f"Subscription to {plan['plan_name']}",
        })

    await db.commit()
    return success_response(sub, "Subscription activated.", 201)


@router.post("/{sub_id}/cancel")
async def cancel(sub_id: int, body: CancelRequest, db: DBConn, current_user: CurrentUser):
    sub = await cancel_subscription(db, sub_id, current_user["id"], body.reason)
    if not sub:
        raise NotFoundException("Subscription or not eligible for cancellation")
    await db.commit()
    return success_response(sub, "Subscription cancelled.")


# ─── Admin ────────────────────────────────────────────────────────────────────

@router.get("/admin/all", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def all_subscriptions(
    db: DBConn,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    from app.database.queries.admin_queries import list_subscriptions_admin
    rows, total = await list_subscriptions_admin(db, status, page, limit)
    return success_response(paginated_response(rows, total, page, limit))
