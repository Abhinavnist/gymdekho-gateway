"""
Razorpay webhook handler.
Razorpay sends events to POST /api/v1/webhooks/razorpay with HMAC-SHA256 signature.
"""
import hashlib
import hmac
import logging
from datetime import date

from fastapi import APIRouter, Request, HTTPException
from app.config import settings
from app.database.connection import get_connection
from app.database.queries.subscription_queries_ext import (
    get_subscription_by_id, create_payment_transaction,
)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)


def _verify_razorpay_signature(body: bytes, signature: str) -> bool:
    if not settings.razorpay_webhook_secret:
        logger.warning("Razorpay webhook secret not set — skipping verification (dev mode).")
        return True
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/razorpay")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not _verify_razorpay_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    try:
        import json
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = payload.get("event")
    logger.info("Razorpay webhook received: %s", event)

    async with get_connection() as db:
        if event == "payment.captured":
            await _handle_payment_captured(db, payload)
        elif event == "payment.failed":
            await _handle_payment_failed(db, payload)
        elif event == "subscription.activated":
            await _handle_subscription_activated(db, payload)
        elif event == "subscription.cancelled":
            await _handle_subscription_cancelled(db, payload)
        else:
            logger.info("Unhandled Razorpay event: %s", event)

    return {"status": "ok"}


async def _handle_payment_captured(db, payload: dict):
    import secrets
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment.get("notes", {})
    subscription_id = notes.get("subscription_id")
    user_id = notes.get("user_id")

    if not subscription_id or not user_id:
        logger.warning("payment.captured missing subscription_id or user_id in notes")
        return

    await create_payment_transaction(db, {
        "user_id": int(user_id),
        "subscription_id": int(subscription_id),
        "transaction_id": f"RZP-{secrets.token_hex(8).upper()}",
        "transaction_type": "SUBSCRIPTION",
        "amount": payment.get("amount", 0) / 100,
        "currency": payment.get("currency", "INR"),
        "base_amount": payment.get("amount", 0) / 100,
        "payment_method": payment.get("method"),
        "payment_gateway": "RAZORPAY",
        "status": "SUCCESS",
        "payment_date": date.today(),
        "description": f"Razorpay payment {payment.get('id')}",
    })

    # Activate subscription
    async with db.cursor() as cur:
        await cur.execute(
            "UPDATE user_subscriptions SET status = 'ACTIVE', updated_at = NOW() WHERE id = %s",
            (int(subscription_id),),
        )
    await db.commit()
    logger.info("Subscription %s activated via webhook", subscription_id)


async def _handle_payment_failed(db, payload: dict):
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment.get("notes", {})
    subscription_id = notes.get("subscription_id")
    if subscription_id:
        async with db.cursor() as cur:
            await cur.execute(
                "UPDATE user_subscriptions SET status = 'PAST_DUE', failed_payment_attempts = failed_payment_attempts + 1 WHERE id = %s",
                (int(subscription_id),),
            )
        await db.commit()


async def _handle_subscription_activated(db, payload: dict):
    sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    notes = sub_entity.get("notes", {})
    subscription_id = notes.get("subscription_id")
    if subscription_id:
        async with db.cursor() as cur:
            await cur.execute(
                "UPDATE user_subscriptions SET status = 'ACTIVE', updated_at = NOW() WHERE id = %s",
                (int(subscription_id),),
            )
        await db.commit()


async def _handle_subscription_cancelled(db, payload: dict):
    sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    notes = sub_entity.get("notes", {})
    subscription_id = notes.get("subscription_id")
    if subscription_id:
        async with db.cursor() as cur:
            await cur.execute(
                "UPDATE user_subscriptions SET status = 'CANCELLED', cancellation_date = CURRENT_DATE, updated_at = NOW() WHERE id = %s",
                (int(subscription_id),),
            )
        await db.commit()
