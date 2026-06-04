import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
) -> bool:
    if not settings.sendgrid_api_key:
        logger.warning("SendGrid API key not configured. Email not sent.")
        return False
    try:
        message = Mail(
            from_email=(settings.sendgrid_from_email, settings.sendgrid_from_name),
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        logger.info("Email sent to %s | status=%s", to_email, response.status_code)
        return response.status_code in (200, 202)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


# ─── Email Templates ──────────────────────────────────────────────────────────

def welcome_email_html(name: str) -> str:
    return f"""
    <h2>Welcome to GymConnect AI, {name}! 🎉</h2>
    <p>Your account has been created successfully.</p>
    <p>Start exploring gyms and trainers near you.</p>
    """


def otp_email_html(name: str, otp: str) -> str:
    return f"""
    <h2>Hi {name},</h2>
    <p>Your email verification OTP is:</p>
    <h1 style="letter-spacing:8px;">{otp}</h1>
    <p>This OTP expires in 10 minutes.</p>
    """


def password_reset_email_html(name: str, reset_link: str) -> str:
    return f"""
    <h2>Hi {name},</h2>
    <p>Click the link below to reset your password:</p>
    <a href="{reset_link}" style="padding:10px 20px;background:#000;color:#fff;text-decoration:none;border-radius:4px;">
        Reset Password
    </a>
    <p>This link expires in 1 hour. If you did not request this, ignore this email.</p>
    """


def verification_email_html(name: str, verify_link: str) -> str:
    return f"""
    <h2>Hi {name},</h2>
    <p>Please verify your email address to activate your GymConnect AI account.</p>
    <a href="{verify_link}" style="padding:12px 24px;background:#000;color:#fff;text-decoration:none;border-radius:6px;display:inline-block;margin:16px 0;">
        Verify Email
    </a>
    <p>This link expires in 24 hours. If you did not create an account, ignore this email.</p>
    """


def membership_expiry_email_html(member_name: str, gym_name: str, expiry_date: str) -> str:
    return f"""
    <h2>Hi {member_name},</h2>
    <p>Your membership at <strong>{gym_name}</strong> expires on <strong>{expiry_date}</strong>.</p>
    <p>Renew now to continue enjoying your fitness journey!</p>
    """
