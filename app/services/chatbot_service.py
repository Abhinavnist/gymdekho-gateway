"""
Chatbot service — Lead-first AI assistant.

FLOW:
  1. Greet visitor → ask what they need
  2. On ANY question about plans / pricing / hours / facilities:
     → Ask for name + phone FIRST (if not already collected)
  3. After lead captured → answer using ONLY real gym data
  4. If data missing → give gym phone number, don't make up anything
  5. All replies ≤ 2 short sentences
"""
import json
import logging
import re
import psycopg
import google.generativeai as genai

from app.config import settings
from app.core.exceptions import NotFoundException, SubscriptionLimitException
from app.database.queries import chatbot_queries, lead_queries, subscription_queries
from app.utils.whatsapp import new_lead_message, send_whatsapp

logger = logging.getLogger(__name__)
_gemini_configured = False


def _get_gemini_model():
    global _gemini_configured
    if not _gemini_configured:
        genai.configure(api_key=settings.gemini_api_key)
        _gemini_configured = True
    # Use system_instruction so rules persist across every turn
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,       # low = more focused, less creative
            max_output_tokens=300, # enough for 2-3 complete sentences
        ),
    )


def _has_lead(history: list[dict], current_message: str = "") -> bool:
    """Return True if the user already shared a phone number in this session (history or current message)."""
    phone_pattern = re.compile(r'[6-9]\d{9}')
    # Check current message first
    if phone_pattern.search(current_message.replace(" ", "").replace("-", "")):
        return True
    # Check history
    for h in history:
        if h.get("role") == "user":
            text = h.get("content", "").replace(" ", "").replace("-", "")
            if phone_pattern.search(text):
                return True
    return False


def _build_system_prompt(knowledge: dict) -> str:
    gym   = knowledge.get("gym") or {}
    hours = knowledge.get("hours") or []
    plans = knowledge.get("plans") or []
    facs  = knowledge.get("facilities") or []
    cfg   = knowledge.get("chatbot_config") or {}

    gym_name  = gym.get("gym_name", "this gym")
    phone     = gym.get("whatsapp_number") or gym.get("phone_number") or "the gym directly"
    bot_name  = cfg.get("bot_name") or "GymBot"

    # ── Hours block ──
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if hours:
        hours_lines = []
        for h in hours:
            day = days[h["day_of_week"]] if 0 <= h.get("day_of_week", -1) < 7 else "?"
            if not h.get("is_open"):
                hours_lines.append(f"{day}: Closed")
            elif h.get("is_24_hours"):
                hours_lines.append(f"{day}: Open 24 hours")
            else:
                hours_lines.append(f"{day}: {h.get('opening_time','?')} – {h.get('closing_time','?')}")
        hours_block = "\n".join(hours_lines)
    else:
        hours_block = "NOT SET — tell user to call the gym for timings"

    # ── Plans block ──
    if plans:
        plan_lines = []
        for p in plans:
            price = p.get("discounted_price") or p.get("original_price") or "?"
            plan_lines.append(f"- {p['plan_name']}: ₹{price} / {p['duration_months']} month(s)")
            if p.get("trial_available") and p.get("trial_duration_days"):
                plan_lines.append(f"  (Free trial: {p['trial_duration_days']} days)")
        plans_block = "\n".join(plan_lines)
    else:
        plans_block = "NOT SET — tell user to call the gym for pricing"

    # ── Facilities block ──
    if facs:
        fac_names = ", ".join(f["facility_name"] for f in facs)
    else:
        fac_names = "NOT SET — tell user to call the gym for facility details"

    # ── Custom FAQs ──
    faq_block = ""
    raw_faqs = cfg.get("custom_faqs")
    if raw_faqs:
        if isinstance(raw_faqs, str):
            try: raw_faqs = json.loads(raw_faqs)
            except: raw_faqs = []
        if isinstance(raw_faqs, list):
            lines = []
            for f in raw_faqs:
                q = f.get("question") or f.get("q") or ""
                a = f.get("answer") or f.get("a") or ""
                if q and a:
                    lines.append(f"Q: {q}\nA: {a}")
            if lines:
                faq_block = "CUSTOM FAQs (always use these answers):\n" + "\n\n".join(lines)

    return f"""You are {bot_name}, the WhatsApp-style chat assistant for {gym_name}.

GYM CONTACT:
  Phone/WhatsApp: {phone}
  Address: {gym.get('full_address','')}, {gym.get('city','')}, {gym.get('state','')}

OPERATING HOURS:
{hours_block}

MEMBERSHIP PLANS:
{plans_block}

FACILITIES:
{fac_names}

{faq_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES — NEVER BREAK THESE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RULE 1 — LEAD FIRST (most important):
  Before answering ANY question about plans, pricing, timings, facilities, joining, trials, or discounts —
  you MUST first ask: "Sure! Could you share your name and phone number so I can help you better? 😊"
  Only AFTER the user shares their name AND phone number, answer their question.
  Exception: if the user already shared their phone number earlier in this conversation, skip asking again.

RULE 2 — ONLY USE REAL DATA:
  If the data above says "NOT SET", DO NOT make up an answer.
  Instead say: "I don't have that info right now — please call us at {phone} 📞"

RULE 3 — SHORT ANSWERS ONLY:
  Maximum 2 sentences per reply. No bullet lists. No long paragraphs.
  Be conversational, like a real WhatsApp chat.

RULE 4 — STAY ON TOPIC:
  Only answer questions about THIS gym. If asked about other gyms, say you only know about {gym_name}.

RULE 5 — UNKNOWN QUESTIONS:
  If you don't know something, say: "For that, please contact us at {phone} 📞"

RULE 6 — NEVER PRETEND:
  Don't say "I'll check" or "let me find out". You either have the data or you don't.
"""


def _build_first_message(message: str, system_prompt: str) -> str:
    """Wrap system rules into the first user message since Gemini needs it in conversation."""
    return (
        f"[SYSTEM INSTRUCTIONS — follow these for the entire conversation]\n"
        f"{system_prompt}\n"
        f"[END SYSTEM INSTRUCTIONS]\n\n"
        f"User's first message: {message}"
    )


async def chat(
    db: psycopg.AsyncConnection,
    gym_id: int,
    session_id: str,
    message: str,
    history: list[dict],
) -> str:
    if not settings.gemini_api_key:
        knowledge = await chatbot_queries.build_gym_knowledge_base(db, gym_id)
        gym = knowledge.get("gym") or {}
        phone = gym.get("phone_number", "the gym")
        return f"Hi! Our assistant is offline. Please contact us at {phone} 📞"

    knowledge = await chatbot_queries.build_gym_knowledge_base(db, gym_id)
    if not knowledge.get("gym"):
        raise NotFoundException("Gym")

    gym   = knowledge.get("gym") or {}
    phone = gym.get("whatsapp_number") or gym.get("phone_number") or "the gym"

    system_prompt = _build_system_prompt(knowledge)

    try:
        model = _get_gemini_model()

        # Build Gemini history from past turns
        gemini_history = []
        for h in history[-12:]:  # keep last 12 turns for context
            role = "user" if h["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [h["content"]]})

        chat_session = model.start_chat(history=gemini_history)

        lead_collected = _has_lead(history, message)
        lead_status = (
            "[Contact info already collected — answer questions using gym data below.]\n"
            if lead_collected else
            "[Contact NOT collected — if user asks about plans/pricing/timings/facilities/joining, ask for name+phone BEFORE answering.]\n"
        )

        if not history:
            # First message — inject full system instructions + lead status
            full_message = _build_first_message(message, system_prompt)
        else:
            # All subsequent messages — always include system context + lead status
            full_message = (
                f"[SYSTEM — follow these rules for every reply]\n"
                f"{system_prompt}\n"
                f"{lead_status}"
                f"[END SYSTEM]\n\n"
                f"User: {message}"
            )

        response = chat_session.send_message(full_message)
        reply = response.text.strip()

        # Safety: if model ignored token limit and gave a very long reply, trim it
        # Only trim if clearly too long (> 300 chars), to avoid cutting short replies
        if len(reply) > 300:
            sentences = re.split(r'(?<=[.!?])\s+', reply)
            if len(sentences) > 3:
                reply = " ".join(sentences[:2]).strip()

        return reply

    except Exception as exc:
        logger.error("Gemini chat error gym=%s: %s", gym_id, exc)
        return f"Sorry, I'm having trouble right now. Please contact us at {phone} 📞"


async def capture_lead(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    limit_info = await subscription_queries.check_gym_lead_limit(db, gym_id)
    if not limit_info["within_limit"]:
        raise SubscriptionLimitException("Monthly lead limit reached. Please upgrade your plan.")

    lead_data = {
        "gym_id":           gym_id,
        "trainer_id":       None,
        "lead_name":        data["lead_name"],
        "phone":            data["phone"],
        "email":            data.get("email"),
        "age_range":        data.get("age_range"),
        "gender":           data.get("gender"),
        "location":         data.get("location"),
        "initial_query":    data.get("initial_query"),
        "chat_transcript":  json.dumps(data.get("chat_transcript", [])),
        "lead_source":      data.get("lead_source", "CHATBOT"),
        "interested_services": json.dumps(data.get("interested_services", {})),
        "budget_range":     data.get("budget_range"),
        "preferred_timing": data.get("preferred_timing"),
        "fitness_goals":    json.dumps(data.get("fitness_goals", {})),
        "utm_source":       data.get("utm_source"),
        "utm_medium":       data.get("utm_medium"),
        "utm_campaign":     data.get("utm_campaign"),
        "prefers_whatsapp": True,
        "prefers_email":    bool(data.get("email")),
        "lead_score":       _calculate_lead_score(data),
    }

    lead = await lead_queries.create_lead(db, lead_data)
    await subscription_queries.increment_lead_usage(db, gym_id)
    await db.commit()

    # Notify gym owner on WhatsApp
    gym_info = await chatbot_queries.build_gym_knowledge_base(db, gym_id)
    gym = gym_info.get("gym")
    if gym and gym.get("whatsapp_number"):
        msg = new_lead_message(gym["gym_name"], data["lead_name"], data["phone"])
        await send_whatsapp(gym["whatsapp_number"], msg)

    logger.info("Lead captured gym=%s name=%s phone=%s", gym_id, data["lead_name"], data["phone"])
    return lead


def _calculate_lead_score(data: dict) -> int:
    score = 20
    if data.get("phone"):               score += 20
    if data.get("email"):               score += 10
    if data.get("interested_services"): score += 15
    if data.get("budget_range"):        score += 15
    if data.get("preferred_timing"):    score += 10
    if data.get("fitness_goals"):       score += 10
    return min(score, 100)


async def get_chatbot_config(db: psycopg.AsyncConnection, gym_id: int) -> dict:
    config = await chatbot_queries.get_chatbot_config(db, gym_id)
    if not config:
        raise NotFoundException("Chatbot config not found. Please set it up first.")
    return config


async def update_chatbot_config(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    defaults = {
        "bot_name": "GymBot",
        "greeting_message": "Hi! 👋 Welcome! How can I help you today?",
        "response_tone": "FRIENDLY",
        "bot_avatar_url": None,
        "collect_leads": True,
        "escalate_to_human": True,
        "custom_faqs": json.dumps([]),
        "knowledge_base": json.dumps({}),
        "response_templates": json.dumps({}),
        "supported_languages": ["en"],
        "can_book_demos": True,
        "can_check_availability": True,
        "can_share_pricing": True,
        "primary_cta": "Could you share your name and phone number so our team can assist you?",
        "secondary_cta": "Would you like to schedule a free demo session?",
        "active_hours": json.dumps({}),
        "conversation_timeout_minutes": 30,
        "is_active": True,
    }
    merged = {**defaults, **{k: v for k, v in data.items() if v is not None}}
    if isinstance(merged.get("custom_faqs"), list):
        merged["custom_faqs"] = json.dumps(merged["custom_faqs"])
    config = await chatbot_queries.upsert_chatbot_config(db, gym_id, merged)
    await db.commit()
    return config
