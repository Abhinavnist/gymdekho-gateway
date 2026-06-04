from pydantic import BaseModel, Field
from datetime import date


class ChatbotMessageRequest(BaseModel):
    gym_id: int
    session_id: str
    message: str = Field(..., min_length=1, max_length=2000)
    user_name: str | None = None
    user_phone: str | None = None
    history: list[dict] | None = None  # full conversation history from frontend


class LeadCaptureRequest(BaseModel):
    gym_id: int
    lead_name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=10)
    email: str | None = None
    initial_query: str | None = None
    chat_transcript: list[dict] | None = None
    interested_services: dict | None = None
    budget_range: str | None = None
    preferred_timing: str | None = None
    fitness_goals: dict | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    lead_source: str = "CHATBOT"


class LeadUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: int | None = None
    follow_up_date: date | None = None
    follow_up_notes: str | None = None
    increment_contact: int | None = None


class LeadInteractionRequest(BaseModel):
    interaction_type: str = Field(..., pattern="^(CALL|EMAIL|WHATSAPP|VISIT|NOTE|DEMO)$")
    subject: str | None = None
    content: str = Field(..., min_length=2)
    outcome: str | None = None
    next_action: str | None = None
    next_action_date: date | None = None


class ChatbotConfigRequest(BaseModel):
    bot_name: str | None = Field(default=None, max_length=100)
    greeting_message: str | None = None
    response_tone: str | None = Field(default=None, pattern="^(FRIENDLY|FORMAL|HUMOROUS)$")
    bot_avatar_url: str | None = None
    collect_leads: bool = True
    escalate_to_human: bool = True
    custom_faqs: list[dict] | None = None
    primary_cta: str | None = None
    secondary_cta: str | None = None
    can_book_demos: bool = True
    can_share_pricing: bool = True
    is_active: bool = True
