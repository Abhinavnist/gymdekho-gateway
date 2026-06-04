from fastapi import APIRouter
from app.api.v1 import auth, gyms, members, leads, chatbot, notifications, reviews, subscriptions, checkins, uploads, admin, webhooks

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(gyms.router)
api_router.include_router(members.router)
api_router.include_router(leads.router)
api_router.include_router(chatbot.router)
api_router.include_router(notifications.router)
api_router.include_router(reviews.router)
api_router.include_router(subscriptions.router)
api_router.include_router(checkins.router)
api_router.include_router(uploads.router)
api_router.include_router(admin.router)
api_router.include_router(webhooks.router)
