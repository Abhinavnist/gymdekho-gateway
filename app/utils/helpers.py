import re
import secrets
import string
from datetime import date, datetime


def generate_random_token(length: int = 64) -> str:
    return secrets.token_urlsafe(length)


def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def slugify(text: str) -> str:
    from slugify import slugify as _slugify
    return _slugify(text)


def sanitize_phone(phone: str) -> str:
    """Strip all non-digit characters, keep leading + if present."""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("0"):
        cleaned = "+91" + cleaned[1:]
    return cleaned


def days_until(target_date: date) -> int:
    return (target_date - date.today()).days


def format_currency(amount: float, currency: str = "INR") -> str:
    if currency == "INR":
        return f"₹{amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def mask_phone(phone: str) -> str:
    """Return phone with middle digits masked: +91XXXXXX1234"""
    if len(phone) < 6:
        return phone
    return phone[:3] + "X" * (len(phone) - 6) + phone[-4:]


def mask_email(email: str) -> str:
    """Return email with local part partially masked: j***e@gmail.com"""
    parts = email.split("@")
    if len(parts) != 2:
        return email
    local = parts[0]
    masked = local[0] + "***" + local[-1] if len(local) > 2 else local
    return f"{masked}@{parts[1]}"


def is_valid_indian_phone(phone: str) -> bool:
    cleaned = re.sub(r"\D", "", phone)
    if cleaned.startswith("91"):
        cleaned = cleaned[2:]
    return bool(re.match(r"^[6-9]\d{9}$", cleaned))
