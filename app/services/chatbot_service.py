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
import asyncio
import json
import logging
import re
import psycopg
import google.generativeai as genai
from google.api_core import exceptions as g_exceptions

from app.config import settings
from app.core.exceptions import NotFoundException, SubscriptionLimitException
from app.database.queries import chatbot_queries, lead_queries, subscription_queries
from app.utils.whatsapp import new_lead_message, send_whatsapp

logger = logging.getLogger(__name__)
_gemini_configured = False


# ── Tool the model can actually call ──────────────────────────────────────────
# When the visitor shares BOTH name and phone, the model calls this instead of
# just writing text — so the lead gets saved to the DB for real (see _run_capture_lead).
_CAPTURE_LEAD_TOOL = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="capture_lead",
            description=(
                "Save the visitor's contact details as a lead. Call this the MOMENT "
                "the visitor has provided BOTH their name AND a valid phone number. "
                "Do not call it before you have both."
            ),
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "name": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="The visitor's name.",
                    ),
                    "phone": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="The visitor's phone number (digits only).",
                    ),
                    "initial_query": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="What the visitor originally asked about (plans, pricing, timings, etc.).",
                    ),
                },
                required=["name", "phone"],
            ),
        )
    ]
)


def _get_gemini_model(system_prompt: str):
    global _gemini_configured
    if not _gemini_configured:
        genai.configure(api_key=settings.gemini_api_key)
        _gemini_configured = True
    # system_instruction => rules live in Gemini's dedicated rules slot (persist every
    # turn, no re-pasting into user messages). tools => the model can save leads for real.
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_prompt,
        tools=[_CAPTURE_LEAD_TOOL],
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,       # low = more focused, less creative
            max_output_tokens=300, # enough for 2-3 complete sentences
        ),
    )


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


async def _send(chat_session, content, retries: int = 1):
    """Send to Gemini off the event loop, with one retry on transient rate-limit (429)."""
    for attempt in range(retries + 1):
        try:
            return await asyncio.to_thread(chat_session.send_message, content)
        except g_exceptions.ResourceExhausted:
            if attempt < retries:
                await asyncio.sleep(2)
                continue
            raise


def _get_function_call(response):
    """Return the model's function_call part if it wants to call a tool, else None."""
    try:
        for part in response.candidates[0].content.parts:
            fc = getattr(part, "function_call", None)
            if fc and fc.name:
                return fc
    except (IndexError, AttributeError):
        pass
    return None


def _response_text(response) -> str | None:
    """Safely pull text out of a response (response.text raises when a part is a tool call)."""
    try:
        return (response.text or "").strip()
    except Exception:
        try:
            parts = response.candidates[0].content.parts
            texts = [p.text for p in parts if getattr(p, "text", "")]
            return " ".join(texts).strip() or None
        except (IndexError, AttributeError):
            return None


def _clean_phone(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


async def _run_capture_lead(
    db: psycopg.AsyncConnection,
    gym_id: int,
    args: dict,
    current_message: str,
    history: list[dict],
) -> dict:
    """Persist the lead the model asked to capture. Returns a result dict fed back to the model."""
    name  = (args.get("name") or "").strip()
    phone = _clean_phone(args.get("phone", ""))

    # Guard against junk captures: a real Indian mobile is 10 digits (last 10 must
    # start 6-9). Reject too-short/fake numbers like "123" so they don't become leads.
    digits10 = phone[-10:]
    if len(digits10) < 10 or digits10[0] not in "6789":
        return {"saved": False,
                "message": "That phone number looks invalid. Politely ask the visitor for a valid 10-digit mobile number, and do NOT claim you saved their details."}
    if len(name) < 2:
        return {"saved": False,
                "message": "The name is missing. Politely ask the visitor for their name before saving."}

    lead_input = {
        "lead_name":     name,
        "phone":         phone,
        "initial_query": args.get("initial_query") or _first_user_query(history, current_message),
        "chat_transcript": history + [{"role": "user", "content": current_message}],
        "lead_source":   "CHATBOT",
    }
    try:
        await capture_lead(db, gym_id, lead_input)
        return {"saved": True,
                "message": "Lead saved. Thank the visitor briefly and answer their question using the gym data."}
    except SubscriptionLimitException:
        return {"saved": False,
                "message": "Could not save the lead (monthly limit reached). Apologize briefly and give the gym phone number."}
    except Exception as exc:
        logger.error("capture_lead tool failed gym=%s: %s", gym_id, exc)
        return {"saved": False,
                "message": "Could not save the lead due to an error. Ask them to call the gym directly."}


def _first_user_query(history: list[dict], current_message: str) -> str:
    for h in history:
        if h.get("role") == "user" and h.get("content"):
            return h["content"]
    return current_message


async def chat(
    db: psycopg.AsyncConnection,
    gym_id: int,
    session_id: str,
    message: str,
    history: list[dict],
    lead_already_captured: bool = False,
) -> tuple[str, bool]:
    """Return (reply_text, lead_captured_this_turn_or_before)."""
    if not settings.gemini_api_key:
        knowledge = await chatbot_queries.build_gym_knowledge_base(db, gym_id)
        gym = knowledge.get("gym") or {}
        phone = gym.get("phone_number", "the gym")
        return f"Hi! Our assistant is offline. Please contact us at {phone} 📞", lead_already_captured

    knowledge = await chatbot_queries.build_gym_knowledge_base(db, gym_id)
    if not knowledge.get("gym"):
        raise NotFoundException("Gym")

    gym   = knowledge.get("gym") or {}
    phone = gym.get("whatsapp_number") or gym.get("phone_number") or "the gym"

    # Real state: only a PRIOR successful capture (tracked in the session) counts.
    # We do NOT infer capture from a phone appearing in the text — that would tell the
    # model to skip the capture_lead tool and the lead would never be saved.
    lead_captured = lead_already_captured

    system_prompt = _build_system_prompt(knowledge)
    if lead_captured:
        system_prompt += (
            "\n\nCURRENT STATUS: This visitor has ALREADY shared their contact details. "
            "Do NOT ask for them again and do NOT call capture_lead. Answer questions directly using the gym data."
        )
    else:
        system_prompt += (
            "\n\nCURRENT STATUS: This visitor has NOT shared contact details yet. Follow RULE 1. "
            "The MOMENT you have BOTH their name AND phone number (even in their very first message), "
            "call capture_lead — do not just reply, you must call the tool to actually save them."
        )

    try:
        model = _get_gemini_model(system_prompt)

        # Build Gemini history from past turns (system rules now live in system_instruction)
        gemini_history = []
        for h in history[-12:]:  # keep last 12 turns for context
            role = "user" if h["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [h["content"]]})

        chat_session = model.start_chat(history=gemini_history)

        # 1st turn: send the plain user message (no prompt re-injection)
        response = await _send(chat_session, message)

        # Tool loop: if the model wants to save a lead, run it and feed the result back
        fc = _get_function_call(response)
        if fc and fc.name == "capture_lead":
            result = await _run_capture_lead(db, gym_id, dict(fc.args), message, history)
            lead_captured = lead_captured or result["saved"]
            response = await _send(
                chat_session,
                genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name="capture_lead", response={"result": result["message"]}
                        )
                    )]
                ),
            )

        reply = _response_text(response)
        if not reply:
            reply = f"Could you tell me a bit more? Or reach us directly at {phone} 📞"
        return reply, lead_captured

    except g_exceptions.ResourceExhausted:
        logger.warning("Gemini rate limit hit gym=%s (free-tier quota)", gym_id)
        return "We're getting a lot of messages right now 🙏 Please try again in a few seconds.", lead_captured
    except Exception as exc:
        logger.error("Gemini chat error gym=%s: %s", gym_id, exc)
        return f"Sorry, I'm having trouble right now. Please contact us at {phone} 📞", lead_captured


async def capture_lead(db: psycopg.AsyncConnection, gym_id: int, data: dict) -> dict:
    # Dedup: a returning visitor (new session, or after a server restart) must not
    # create a second lead for the same phone. Check before the limit/usage counters.
    existing = await lead_queries.get_lead_by_phone(db, gym_id, data.get("phone", ""))
    if existing:
        logger.info("Duplicate lead skipped gym=%s phone=%s (existing id=%s)",
                    gym_id, data.get("phone"), existing.get("id"))
        return existing

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
