import json
from datetime import date, timedelta
import secrets
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from app.core.dependencies import DBConn, CurrentUser, require_roles
from app.database.queries.admin_queries import (
    get_platform_stats, list_users, get_user_detail, set_user_active,
    unlock_user, list_gyms_admin, reject_gym, get_system_settings, update_system_setting,
)
from app.services import gym_service
from app.core.exceptions import NotFoundException, ValidationException
from app.utils.response import success_response
from app.utils.pagination import paginated_response
import psycopg

router = APIRouter(prefix="/admin", tags=["Admin"])
AdminUser = Depends(require_roles("SUPER_ADMIN", "ADMIN"))


# ─── Request Models ───────────────────────────────────────────────────────────

class SystemSettingUpdate(BaseModel):
    value: str | bool | int | float
    def str_value(self) -> str:
        return str(self.value).lower() if isinstance(self.value, bool) else str(self.value)

class GymRejectRequest(BaseModel):
    reason: str | None = None

class GymEditRequest(BaseModel):
    gym_name: str | None = None
    phone_number: str | None = None
    business_email: str | None = None
    full_address: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None
    website: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    gym_type: str | None = None
    max_capacity: int | None = None
    total_area_sqft: int | None = None
    amenities: dict | None = None
    featured_listing: bool | None = None
    meta_title: str | None = None
    meta_description: str | None = None

class ManualSubscriptionRequest(BaseModel):
    plan_id: int
    months: int = 1
    reason: str | None = None

class PlanUpdateRequest(BaseModel):
    plan_name: str | None = None
    description: str | None = None
    base_price: float | None = None
    max_leads_per_month: int | None = None
    max_members: int | None = None
    max_whatsapp_messages: int | None = None
    features: dict | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    sort_order: int | None = None

class GymFeatureOverrideRequest(BaseModel):
    """Admin can override specific limits/features for a gym regardless of plan."""
    max_leads_override: int | None = None        # -1 = unlimited
    max_members_override: int | None = None      # -1 = unlimited
    max_whatsapp_override: int | None = None     # -1 = unlimited
    chatbot_enabled: bool | None = None
    analytics_enabled: bool | None = None
    featured_listing: bool | None = None
    notes: str | None = None

class UserRoleRequest(BaseModel):
    role: str  # MEMBER, GYM_OWNER, GYM_MANAGER, ADMIN


# ─── 1. PLATFORM STATS ───────────────────────────────────────────────────────

@router.get("/stats", dependencies=[AdminUser])
async def platform_stats(db: DBConn):
    stats = await get_platform_stats(db)
    return success_response(stats)


# ─── 2. USER MANAGEMENT ──────────────────────────────────────────────────────

@router.get("/users", dependencies=[AdminUser])
async def list_all_users(
    db: DBConn,
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    rows, total = await list_users(db, role, is_active, search, page, limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.get("/users/{user_id}", dependencies=[AdminUser])
async def get_user(user_id: int, db: DBConn):
    user = await get_user_detail(db, user_id)
    if not user:
        raise NotFoundException("User")
    return success_response(user)


@router.patch("/users/{user_id}/activate", dependencies=[AdminUser])
async def activate_user(user_id: int, db: DBConn):
    user = await set_user_active(db, user_id, True)
    await db.commit()
    return success_response(user, "User activated.")


@router.patch("/users/{user_id}/deactivate", dependencies=[AdminUser])
async def deactivate_user(user_id: int, db: DBConn):
    user = await set_user_active(db, user_id, False)
    await db.commit()
    return success_response(user, "User deactivated.")


@router.patch("/users/{user_id}/unlock", dependencies=[AdminUser])
async def unlock(user_id: int, db: DBConn):
    user = await unlock_user(db, user_id)
    await db.commit()
    return success_response(user, "Account unlocked.")


@router.patch("/users/{user_id}/role", dependencies=[AdminUser])
async def change_user_role(user_id: int, body: UserRoleRequest, db: DBConn):
    """Admin can change a user's role (e.g. promote to ADMIN, demote to MEMBER)."""
    allowed = {"MEMBER", "GYM_OWNER", "GYM_MANAGER", "TRAINER", "ADMIN"}
    if body.role not in allowed:
        raise ValidationException(f"Role must be one of: {', '.join(allowed)}")
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "UPDATE users SET role = %s, updated_at = NOW() WHERE id = %s RETURNING id, email, full_name, role",
            (body.role, user_id),
        )
        user = await cur.fetchone()
    if not user:
        raise NotFoundException("User")
    await db.commit()
    return success_response(user, f"Role changed to {body.role}.")


@router.post("/users/{user_id}/reset-password-link", dependencies=[AdminUser])
async def send_password_reset(user_id: int, db: DBConn):
    """Admin triggers a password reset email for any user."""
    from app.services import auth_service
    from app.database.queries import user_queries
    user = await user_queries.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundException("User")
    if not user.get("email"):
        raise ValidationException("User has no email address.")
    await auth_service.forgot_password(db, user["email"])
    return success_response(message=f"Password reset link sent to {user['email']}.")


# ─── 3. GYM MANAGEMENT ───────────────────────────────────────────────────────

@router.get("/gyms", dependencies=[AdminUser])
async def list_gyms(
    db: DBConn,
    approval_status: str | None = Query(None, pattern="^(PENDING|APPROVED|REJECTED|SUSPENDED)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    rows, total = await list_gyms_admin(db, approval_status, page, limit)
    return success_response(paginated_response(rows, total, page, limit))


@router.post("/gyms/{gym_id}/approve", dependencies=[AdminUser])
async def approve_gym(gym_id: int, db: DBConn):
    await gym_service.approve_gym(db, gym_id)
    return success_response(message="Gym approved.")


@router.post("/gyms/{gym_id}/reject", dependencies=[AdminUser])
async def reject(gym_id: int, body: GymRejectRequest, db: DBConn):
    gym = await reject_gym(db, gym_id, body.reason)
    if not gym:
        raise NotFoundException("Gym")
    await db.commit()
    return success_response(gym, "Gym rejected.")


@router.patch("/gyms/{gym_id}/reinstate", dependencies=[AdminUser])
async def reinstate_gym(gym_id: int, db: DBConn):
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "UPDATE gyms SET approval_status = 'APPROVED', rejection_reason = NULL, updated_at = NOW() WHERE id = %s RETURNING id, gym_name, approval_status",
            (gym_id,),
        )
        gym = await cur.fetchone()
    await db.commit()
    if not gym:
        raise NotFoundException("Gym")
    return success_response(gym, "Gym reinstated.")


@router.patch("/gyms/{gym_id}/suspend", dependencies=[AdminUser])
async def suspend_gym(gym_id: int, db: DBConn):
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "UPDATE gyms SET approval_status = 'SUSPENDED', updated_at = NOW() WHERE id = %s RETURNING id, gym_name, approval_status",
            (gym_id,),
        )
        gym = await cur.fetchone()
    await db.commit()
    if not gym:
        raise NotFoundException("Gym")
    return success_response(gym, "Gym suspended.")


@router.patch("/gyms/{gym_id}/edit", dependencies=[AdminUser])
async def edit_gym(gym_id: int, body: GymEditRequest, db: DBConn):
    """Admin can edit any gym's data directly."""
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise ValidationException("No fields to update.")
    if "amenities" in fields:
        fields["amenities"] = json.dumps(fields["amenities"])
    set_clause = ", ".join(f"{k} = %({k})s" for k in fields)
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"UPDATE gyms SET {set_clause}, updated_at = NOW() WHERE id = %(gym_id)s RETURNING id, gym_name, city, approval_status, featured_listing",
            {**fields, "gym_id": gym_id},
        )
        gym = await cur.fetchone()
    if not gym:
        raise NotFoundException("Gym")
    await db.commit()
    return success_response(gym, "Gym updated.")


@router.patch("/gyms/{gym_id}/feature-override", dependencies=[AdminUser])
async def override_gym_features(gym_id: int, body: GymFeatureOverrideRequest, db: DBConn):
    """
    Admin can override limits/features for a specific gym regardless of their plan.
    Stored in gym_feature_overrides table.
    Use -1 for unlimited. Use null to remove the override (revert to plan default).
    """
    overrides = body.model_dump(exclude_none=True)
    notes = overrides.pop("notes", None)

    # Store overrides in the gyms table directly (simpler approach)
    updates = {}
    if "featured_listing" in overrides:
        updates["featured_listing"] = overrides["featured_listing"]

    # For limit overrides, store in a JSON column or separate table
    # We'll use the gym's subscription record to update limits
    if any(k in overrides for k in ["max_leads_override", "max_members_override", "max_whatsapp_override"]):
        async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                """
                UPDATE user_subscriptions
                SET
                    override_leads = %(leads)s,
                    override_members = %(members)s,
                    override_whatsapp = %(whatsapp)s,
                    admin_notes = %(notes)s,
                    updated_at = NOW()
                WHERE gym_id = %s AND status IN ('ACTIVE','TRIAL')
                RETURNING id
                """,
                {
                    "leads": overrides.get("max_leads_override"),
                    "members": overrides.get("max_members_override"),
                    "whatsapp": overrides.get("max_whatsapp_override"),
                    "notes": notes,
                },
            )

    if updates:
        set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
        async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                f"UPDATE gyms SET {set_clause}, updated_at = NOW() WHERE id = %(gym_id)s",
                {**updates, "gym_id": gym_id},
            )

    await db.commit()
    return success_response({"gym_id": gym_id, "overrides_applied": overrides}, "Feature overrides applied.")


@router.post("/gyms/{gym_id}/grant-subscription", dependencies=[AdminUser])
async def grant_subscription(gym_id: int, body: ManualSubscriptionRequest, db: DBConn):
    """
    Admin manually assigns any plan to a gym (free upgrade, support resolution, etc.)
    This overrides any existing subscription.
    """
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        # Validate plan exists
        await cur.execute("SELECT * FROM subscription_plans WHERE id = %s", (body.plan_id,))
        plan = await cur.fetchone()
        if not plan:
            raise NotFoundException("Plan")

        # Validate gym exists
        await cur.execute("SELECT id, gym_name FROM gyms WHERE id = %s", (gym_id,))
        gym = await cur.fetchone()
        if not gym:
            raise NotFoundException("Gym")

        # Get gym owner
        await cur.execute("SELECT owner_user_id FROM gyms WHERE id = %s", (gym_id,))
        owner = await cur.fetchone()

        # Cancel existing active subscriptions for this gym
        await cur.execute(
            "UPDATE user_subscriptions SET status = 'CANCELLED', updated_at = NOW() WHERE gym_id = %s AND status IN ('ACTIVE','TRIAL')",
            (gym_id,),
        )

        # Create new subscription
        today = date.today()
        period_end = today + timedelta(days=body.months * 30)
        sub_code = f"ADMIN-{secrets.token_hex(6).upper()}"

        await cur.execute(
            """
            INSERT INTO user_subscriptions (
                user_id, gym_id, plan_id, subscription_code, status,
                current_period_start, current_period_end,
                amount_per_cycle, total_amount, auto_renewal, next_billing_date,
                admin_notes
            ) VALUES (
                %s, %s, %s, %s, 'ACTIVE',
                %s, %s,
                0, 0, FALSE, %s,
                %s
            )
            RETURNING *
            """,
            (
                owner["owner_user_id"], gym_id, body.plan_id, sub_code,
                today, period_end, period_end,
                f"Admin grant: {body.reason or 'Manual assignment'}"
            ),
        )
        sub = await cur.fetchone()

    await db.commit()
    return success_response(sub, f"Plan '{plan['plan_name']}' granted to {gym['gym_name']} for {body.months} month(s).")


@router.delete("/gyms/{gym_id}/subscription", dependencies=[AdminUser])
async def cancel_gym_subscription(gym_id: int, db: DBConn):
    """Admin cancels a gym's active subscription (reverts to free)."""
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            "UPDATE user_subscriptions SET status = 'CANCELLED', updated_at = NOW() WHERE gym_id = %s AND status IN ('ACTIVE','TRIAL') RETURNING id, status",
            (gym_id,),
        )
        result = await cur.fetchone()
    if not result:
        raise NotFoundException("Active subscription")
    await db.commit()
    return success_response(result, "Subscription cancelled. Gym reverted to free plan.")


# ─── 4. SUBSCRIPTION PLAN MANAGEMENT ─────────────────────────────────────────

@router.get("/plans", dependencies=[AdminUser])
async def list_plans(db: DBConn):
    """Admin: view ALL plans including inactive."""
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute("SELECT * FROM subscription_plans ORDER BY sort_order ASC, base_price ASC")
        plans = await cur.fetchall()
    return success_response(plans)


@router.patch("/plans/{plan_id}", dependencies=[AdminUser])
async def update_plan(plan_id: int, body: PlanUpdateRequest, db: DBConn):
    """Admin can edit any platform subscription plan (pricing, limits, features)."""
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise ValidationException("No fields to update.")
    if "features" in fields:
        fields["features"] = json.dumps(fields["features"])
    set_clause = ", ".join(f"{k} = %({k})s" for k in fields)
    async with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            f"UPDATE subscription_plans SET {set_clause}, updated_at = NOW() WHERE id = %(plan_id)s RETURNING *",
            {**fields, "plan_id": plan_id},
        )
        plan = await cur.fetchone()
    if not plan:
        raise NotFoundException("Plan")
    await db.commit()
    return success_response(plan, "Plan updated.")


# ─── 5. SYSTEM SETTINGS ──────────────────────────────────────────────────────

@router.get("/settings", dependencies=[AdminUser])
async def get_settings(db: DBConn):
    settings = await get_system_settings(db)
    return success_response(settings)


@router.put("/settings/{key}", dependencies=[AdminUser])
async def update_setting(key: str, body: SystemSettingUpdate, db: DBConn):
    setting = await update_system_setting(db, key, body.str_value())
    if not setting:
        raise NotFoundException("Setting")
    await db.commit()
    return success_response(setting)
