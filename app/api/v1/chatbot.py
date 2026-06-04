from fastapi import APIRouter
from app.core.dependencies import DBConn, CurrentUser
from app.models.lead import ChatbotMessageRequest, LeadCaptureRequest, ChatbotConfigRequest
from app.services import chatbot_service
from app.utils.response import success_response

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

# In-memory session store (replace with Redis in production)
_sessions: dict[str, list[dict]] = {}


@router.post("/message")
async def chat_message(body: ChatbotMessageRequest, db: DBConn):
    session_key = f"{body.gym_id}:{body.session_id}"

    # Prefer history sent by frontend (more reliable than in-memory store)
    # Fall back to server-side session if frontend didn't send history
    if body.history is not None:
        history = body.history
    else:
        history = _sessions.get(session_key, [])

    reply = await chatbot_service.chat(db, body.gym_id, body.session_id, body.message, history)

    # Always maintain server-side history as backup
    server_history = _sessions.get(session_key, [])
    server_history.append({"role": "user", "content": body.message})
    server_history.append({"role": "assistant", "content": reply})
    _sessions[session_key] = server_history[-20:]

    return success_response({"reply": reply, "session_id": body.session_id})


@router.post("/lead-capture", status_code=201)
async def capture_lead(body: LeadCaptureRequest, db: DBConn):
    lead = await chatbot_service.capture_lead(db, body.gym_id, body.model_dump())
    return success_response(lead, "Lead captured successfully.", 201)


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str, gym_id: int, db: DBConn):
    session_key = f"{gym_id}:{session_id}"
    history = _sessions.get(session_key, [])
    return success_response({"session_id": session_id, "history": history})


# ─── Gym Owner Config ─────────────────────────────────────────────────────────

@router.get("/gyms/{gym_id}/config")
async def get_config(gym_id: int, db: DBConn, current_user: CurrentUser):
    config = await chatbot_service.get_chatbot_config(db, gym_id)
    return success_response(config)


@router.put("/gyms/{gym_id}/config")
async def update_config(gym_id: int, body: ChatbotConfigRequest, db: DBConn, current_user: CurrentUser):
    config = await chatbot_service.update_chatbot_config(db, gym_id, body.model_dump(exclude_none=True))
    return success_response(config)
