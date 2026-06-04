from pydantic import BaseModel, EmailStr, Field
from typing import Any


class GymCreateRequest(BaseModel):
    gym_name: str = Field(..., min_length=2, max_length=255)
    owner_name: str = Field(..., min_length=2, max_length=255)
    business_email: EmailStr
    phone_number: str = Field(..., min_length=10, max_length=20)
    whatsapp_number: str | None = None
    full_address: str = Field(..., min_length=10)
    city: str = Field(..., min_length=2)
    state: str = Field(..., min_length=2)
    country: str = "India"
    zipcode: str = Field(..., min_length=6, max_length=10)
    latitude: float | None = None
    longitude: float | None = None
    gym_type: str | None = None
    establishment_year: int | None = None
    total_area_sqft: int | None = None
    max_capacity: int | None = None
    website: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    amenities: dict | None = None


class GymUpdateRequest(BaseModel):
    gym_name: str | None = None
    phone_number: str | None = None
    whatsapp_number: str | None = None
    full_address: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    website: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    gym_type: str | None = None
    amenities: dict | None = None
    meta_title: str | None = None
    meta_description: str | None = None


class GymPlanCreateRequest(BaseModel):
    plan_name: str = Field(..., min_length=2)
    duration_months: int = Field(..., ge=1, le=24)
    original_price: float = Field(..., gt=0)
    discounted_price: float | None = None
    registration_fee: float = 0
    features: dict = Field(default_factory=dict)
    included_services: list[str] = Field(default_factory=list)
    trainer_sessions_included: int = 0
    trial_available: bool = False
    trial_duration_days: int = 0
    trial_cost: float = 0
    is_active: bool = True
    plan_category: str | None = None


class GymPlanUpdateRequest(BaseModel):
    plan_name: str | None = None
    duration_months: int | None = None
    original_price: float | None = None
    discounted_price: float | None = None
    features: dict | None = None
    is_active: bool | None = None


class OperatingHourItem(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    is_open: bool = True
    opening_time: str | None = None   # "HH:MM"
    closing_time: str | None = None
    is_24_hours: bool = False


class OperatingHoursRequest(BaseModel):
    hours: list[OperatingHourItem] = Field(..., min_length=7, max_length=7)


class FacilityCreateRequest(BaseModel):
    category: str = Field(..., min_length=2)
    facility_name: str = Field(..., min_length=2)
    description: str | None = None
    quantity: int = 1
    is_available: bool = True
    is_premium: bool = False
