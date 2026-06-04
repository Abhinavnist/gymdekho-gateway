from pydantic import BaseModel, EmailStr, Field
from datetime import date


class MemberCreateRequest(BaseModel):
    member_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=10, max_length=20)
    email: EmailStr | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    height_cm: int | None = None
    weight_kg: float | None = None
    fitness_goals: dict | None = None
    dietary_restrictions: list[str] = Field(default_factory=list)
    referral_source: str | None = None
    preferred_workout_time: str | None = None
    interested_classes: list[str] = Field(default_factory=list)
    whatsapp_notifications: bool = True
    email_notifications: bool = True
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemberUpdateRequest(BaseModel):
    member_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    notes: str | None = None
    tags: list[str] | None = None
    fitness_goals: dict | None = None
    whatsapp_notifications: bool | None = None
    email_notifications: bool | None = None


class MemberStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|INACTIVE|SUSPENDED|EXPIRED)$")


class AddMembershipRequest(BaseModel):
    plan_id: int
    start_date: date
    end_date: date
    plan_price: float = Field(..., gt=0)
    discount_applied: float = 0
    total_amount: float = Field(..., gt=0)
    payment_method: str | None = None
    payment_status: str = "PAID"
    payment_date: date | None = None
    trainer_sessions_allocated: int = 0
    notes: str | None = None


class BulkWhatsAppRequest(BaseModel):
    message: str = Field(..., min_length=5, max_length=1000)
    member_ids: list[int] | None = None  # None = send to all whatsapp-enabled members
