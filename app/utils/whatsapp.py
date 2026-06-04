import logging
from twilio.rest import Client

from app.config import settings

logger = logging.getLogger(__name__)


def _get_client() -> Client | None:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("Twilio credentials not configured.")
        return None
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


async def send_whatsapp(to_phone: str, message: str) -> bool:
    """Send a WhatsApp message via Twilio. Phone must include country code e.g. +919876543210"""
    client = _get_client()
    if not client:
        return False
    try:
        to = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone
        msg = client.messages.create(
            body=message,
            from_=settings.twilio_whatsapp_from,
            to=to,
        )
        logger.info("WhatsApp sent to %s | sid=%s", to_phone, msg.sid)
        return True
    except Exception as exc:
        logger.error("Failed to send WhatsApp to %s: %s", to_phone, exc)
        return False


async def send_bulk_whatsapp(phone_numbers: list[str], message: str) -> dict:
    """Send same message to multiple numbers. Returns success/failure counts."""
    results = {"sent": 0, "failed": 0, "failed_numbers": []}
    for phone in phone_numbers:
        success = await send_whatsapp(phone, message)
        if success:
            results["sent"] += 1
        else:
            results["failed"] += 1
            results["failed_numbers"].append(phone)
    return results


# ─── Message Templates ────────────────────────────────────────────────────────

def new_lead_message(gym_name: str, lead_name: str, lead_phone: str) -> str:
    return (
        f"🎯 *New Lead Alert — {gym_name}*\n\n"
        f"👤 Name: {lead_name}\n"
        f"📞 Phone: {lead_phone}\n\n"
        f"Follow up now on GymConnect dashboard!"
    )


def membership_expiry_message(member_name: str, gym_name: str, days_left: int) -> str:
    return (
        f"Hi {member_name}! 👋\n\n"
        f"Your membership at *{gym_name}* expires in *{days_left} days*.\n"
        f"Renew now to keep your streak going! 💪"
    )


def welcome_member_message(member_name: str, gym_name: str) -> str:
    return (
        f"Welcome to *{gym_name}*, {member_name}! 🎉\n\n"
        f"Your membership is now active. We're excited to have you!\n"
        f"See you at the gym! 💪"
    )
