"""
GymConnect AI — Full End-to-End Flow Test
==========================================
Tests the complete system flow for every user type:
  SUPER_ADMIN → ADMIN → GYM_OWNER → GYM_MANAGER → Public (chatbot)

Run with:  python tests/test_full_flow.py
"""

import sys
import json
import uuid
import httpx

BASE = "http://localhost:8000/api/v1"

# ─── Helpers ─────────────────────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
SEP  = "─" * 60

results: list[tuple[str, bool, str]] = []


def check(label: str, response: httpx.Response, expect_status: int = 200) -> dict | None:
    ok = response.status_code == expect_status
    body = {}
    try:
        body = response.json()
    except Exception:
        pass
    results.append((label, ok, f"HTTP {response.status_code}"))
    icon = PASS if ok else FAIL
    if ok:
        print(f"  {icon} {label}")
    else:
        print(f"  {icon} {label}  →  HTTP {response.status_code}  {body.get('message','')}")
    return body if ok else None


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def section(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ─── State shared across tests ──────────────────────────────────────────────

state = {}   # filled as we go


# ─── 1. HEALTH ───────────────────────────────────────────────────────────────

def test_health(c: httpx.Client):
    section("1. HEALTH CHECK")
    r = c.get(f"{BASE}/health")
    check("Health endpoint", r)
    r = c.get(f"{BASE}/version")
    check("Version endpoints", r)


# ─── 2. SUPER ADMIN LOGIN ─────────────────────────────────────────────────────

def test_super_admin_login(c: httpx.Client):
    section("2. SUPER ADMIN — Login")
    r = c.post(f"{BASE}/auth/login", json={
        "email": "ziaparkerzp@gmail.com",
        "password": "Admin@GymConnect2024"
    })
    body = check("SUPER_ADMIN login", r)
    if body:
        state["super_token"] = body["data"]["access_token"]
        state["super_refresh"] = body["data"]["refresh_token"]

    # /me
    r = c.get(f"{BASE}/auth/me", headers=auth_header(state["super_token"]))
    body = check("SUPER_ADMIN /me", r)
    if body:
        state["super_id"] = body["data"]["id"]
        assert body["data"]["role"] == "SUPER_ADMIN", "Role mismatch!"

    # Token refresh
    r = c.post(f"{BASE}/auth/refresh-token", json={"refresh_token": state["super_refresh"]})
    check("Token refresh", r)

    # Profile update
    r = c.put(f"{BASE}/auth/me", headers=auth_header(state["super_token"]), json={
        "bio": "Platform founder"
    })
    check("Profile update", r)


# ─── 3. ADMIN ACCOUNT ─────────────────────────────────────────────────────────

def test_admin_account(c: httpx.Client):
    section("3. ADMIN — Register & Login")
    uid = str(uuid.uuid4())[:8]
    email = f"admin_{uid}@gymconnect.io"
    r = c.post(f"{BASE}/auth/register", json={
        "full_name": "Team Admin",
        "email": email,
        "password": "Admin@Test1234",
        "role": "MEMBER"   # registers as MEMBER, super admin upgrades
    })
    body = check("Register admin user", r, 201)

    # Super admin upgrades this user to ADMIN via DB (simulate via admin deactivate/activate cycle)
    # First get the user id from the list
    r = c.get(f"{BASE}/admin/users", headers=auth_header(state["super_token"]),
              params={"search": email})
    body = check("Admin: list users", r)
    if body and body["data"]["data"]:
        admin_user_id = body["data"]["data"][0]["id"]
        state["admin_user_id"] = admin_user_id

        # In real life super admin would set role via DB — we'll test with the registered user
        # Log them in as MEMBER and note they can't access admin routes
        r = c.post(f"{BASE}/auth/login", json={"email": email, "password": "Admin@Test1234"})
        body = check("Admin user login", r)
        if body:
            state["admin_token"] = body["data"]["access_token"]

    # Verify admin user can't hit protected admin routes (should get 403)
    if state.get("admin_token"):
        r = c.get(f"{BASE}/admin/stats", headers=auth_header(state["admin_token"]))
        ok = r.status_code == 403
        results.append(("MEMBER blocked from /admin/stats", ok, f"HTTP {r.status_code}"))
        print(f"  {'✅' if ok else '❌'} MEMBER correctly blocked from /admin/stats  → HTTP {r.status_code}")


# ─── 4. SUPER ADMIN PLATFORM OPERATIONS ──────────────────────────────────────

def test_super_admin_operations(c: httpx.Client):
    section("4. SUPER ADMIN — Platform Operations")
    h = auth_header(state["super_token"])

    r = c.get(f"{BASE}/admin/stats", headers=h)
    check("Platform stats", r)

    r = c.get(f"{BASE}/admin/users", headers=h)
    check("List all users", r)

    r = c.get(f"{BASE}/admin/users", headers=h, params={"role": "SUPER_ADMIN"})
    check("Filter users by role", r)

    r = c.get(f"{BASE}/admin/gyms", headers=h)
    check("List all gyms", r)

    r = c.get(f"{BASE}/admin/gyms", headers=h, params={"approval_status": "PENDING"})
    check("List PENDING gyms", r)

    r = c.get(f"{BASE}/admin/settings", headers=h)
    check("System settings", r)

    r = c.get(f"{BASE}/subscriptions/admin/all", headers=h)
    check("All subscriptions", r)


# ─── 5. GYM OWNER — Register, Create Gym ─────────────────────────────────────

def test_gym_owner_flow(c: httpx.Client):
    section("5. GYM OWNER — Register & Create Gym")
    uid = str(uuid.uuid4())[:8]
    email = f"gymowner_{uid}@gmail.com"

    # Register
    r = c.post(f"{BASE}/auth/register", json={
        "full_name": "Ravi Sharma",
        "email": email,
        "phone": f"+9198{uid[:8]}",
        "password": "GymOwner@1234",
        "role": "GYM_OWNER",
        "city": "Mumbai",
        "state": "Maharashtra"
    })
    check("GYM_OWNER register", r, 201)

    # Login
    r = c.post(f"{BASE}/auth/login", json={"email": email, "password": "GymOwner@1234"})
    body = check("GYM_OWNER login", r)
    if not body:
        return
    state["owner_token"] = body["data"]["access_token"]
    h = auth_header(state["owner_token"])

    # /me
    r = c.get(f"{BASE}/auth/me", headers=h)
    body = check("GYM_OWNER /me", r)
    if body:
        state["owner_id"] = body["data"]["id"]

    # Create Gym
    r = c.post(f"{BASE}/gyms/", headers=h, json={
        "gym_name": f"FitZone Elite {uid}",
        "owner_name": "Ravi Sharma",
        "business_email": f"fitzone_{uid}@gym.com",
        "phone_number": f"+9190{uid[:8]}",
        "whatsapp_number": f"+9190{uid[:8]}",
        "full_address": "123 MG Road, Bandra West",
        "city": "Mumbai",
        "state": "Maharashtra",
        "country": "India",
        "zipcode": "400050",
        "gym_type": "FITNESS_CENTER",
        "establishment_year": 2020,
        "total_area_sqft": 3000,
        "max_capacity": 150,
        "amenities": {"parking": True, "wifi": True, "locker": True}
    })
    body = check("Create gym", r, 201)
    if body:
        state["gym_id"] = body["data"]["id"]
        state["gym_slug"] = body["data"]["slug"]
        print(f"      Gym ID: {state['gym_id']}  Slug: {state['gym_slug']}")

    # Owner can't access gym until approved — but owner can still manage it
    # My Gyms
    r = c.get(f"{BASE}/gyms/my", headers=h)
    check("GYM_OWNER list own gyms", r)


# ─── 6. SUPER ADMIN APPROVES GYM ─────────────────────────────────────────────

def test_admin_approve_gym(c: httpx.Client):
    section("6. SUPER ADMIN — Approve Gym")
    if not state.get("gym_id"):
        print("  ⚠️  No gym to approve — skipping")
        return
    h = auth_header(state["super_token"])

    # Check gym in pending list
    r = c.get(f"{BASE}/admin/gyms", headers=h, params={"approval_status": "PENDING"})
    body = check("Pending gyms list", r)
    if body:
        gyms = body["data"]["data"]
        print(f"      Found {len(gyms)} pending gym(s)")

    # Approve
    r = c.post(f"{BASE}/admin/gyms/{state['gym_id']}/approve", headers=h)
    check("Admin approve gym", r)

    # Verify gym is now APPROVED
    r = c.get(f"{BASE}/gyms/{state['gym_id']}")
    body = check("Gym now public (APPROVED)", r)
    if body:
        status = body["data"]["approval_status"]
        ok = status == "APPROVED"
        results.append(("Gym approval_status == APPROVED", ok, status))
        print(f"  {'✅' if ok else '❌'} approval_status = {status}")


# ─── 7. GYM SETUP — Plans, Hours, Facilities ─────────────────────────────────

def test_gym_setup(c: httpx.Client):
    section("7. GYM OWNER — Setup (Plans, Hours, Facilities)")
    if not state.get("gym_id"):
        print("  ⚠️  No gym — skipping")
        return
    h = auth_header(state["owner_token"])
    gid = state["gym_id"]

    # Create plans
    r = c.post(f"{BASE}/gyms/{gid}/plans", headers=h, json={
        "plan_name": "Monthly Basic",
        "duration_months": 1,
        "original_price": 1500,
        "discounted_price": 1299,
        "features": {"group_classes": True, "locker": False},
        "trial_available": True,
        "trial_duration_days": 7,
        "trial_cost": 0
    })
    body = check("Create Monthly plan", r, 201)
    if body:
        state["plan_id"] = body["data"]["id"]

    r = c.post(f"{BASE}/gyms/{gid}/plans", headers=h, json={
        "plan_name": "Quarterly Pro",
        "duration_months": 3,
        "original_price": 3999,
        "discounted_price": 3299,
        "features": {"group_classes": True, "locker": True, "trainer_sessions": 4}
    })
    check("Create Quarterly plan", r, 201)

    # Get plans (public)
    r = c.get(f"{BASE}/gyms/{gid}/plans")
    check("Public: get gym plans", r)

    # Set operating hours (all 7 days)
    hours = []
    for day in range(7):
        if day == 0:  # Sunday
            hours.append({"day_of_week": day, "is_open": False, "is_24_hours": False})
        else:
            hours.append({"day_of_week": day, "is_open": True, "opening_time": "06:00", "closing_time": "22:00", "is_24_hours": False})
    r = c.post(f"{BASE}/gyms/{gid}/hours", headers=h, json={"hours": hours})
    check("Set operating hours (7 days)", r)

    # Get hours (public)
    r = c.get(f"{BASE}/gyms/{gid}/hours")
    check("Public: get operating hours", r)

    # Add facilities
    facilities = [
        {"category": "Cardio", "facility_name": "Treadmills", "quantity": 10},
        {"category": "Strength", "facility_name": "Free Weights", "quantity": 1},
        {"category": "Amenities", "facility_name": "Locker Room", "quantity": 1},
        {"category": "Amenities", "facility_name": "Shower Area", "quantity": 1},
    ]
    for f in facilities:
        r = c.post(f"{BASE}/gyms/{gid}/facilities", headers=h, json=f)
        check(f"Add facility: {f['facility_name']}", r, 201)

    # Get facilities (public)
    r = c.get(f"{BASE}/gyms/{gid}/facilities")
    check("Public: get facilities", r)

    # Chatbot config
    r = c.put(f"{BASE}/chatbot/gyms/{gid}/config", headers=h, json={
        "bot_name": "FitBot",
        "greeting_message": "Hi! 👋 Welcome to FitZone! How can I help you today?",
        "response_tone": "FRIENDLY",
        "primary_cta": "Interested in joining? Share your name and phone number!",
        "custom_faqs": [
            {"q": "Do you have parking?", "a": "Yes, free parking is available!"},
            {"q": "Do you offer a trial?", "a": "Yes! 7-day free trial on our Monthly plan."},
        ],
        "collect_leads": True,
        "can_share_pricing": True
    })
    check("Setup chatbot config", r)


# ─── 8. PUBLIC GYM PAGE ───────────────────────────────────────────────────────

def test_public_gym_page(c: httpx.Client):
    section("8. PUBLIC — Gym Discovery & Detail Page")
    gid = state.get("gym_id")
    slug = state.get("gym_slug")

    # Search / list gyms
    r = c.get(f"{BASE}/gyms/", params={"city": "Mumbai"})
    check("Public: search gyms by city", r)

    r = c.get(f"{BASE}/gyms/", params={"search": "FitZone"})
    check("Public: full-text search gyms", r)

    # Get by ID
    r = c.get(f"{BASE}/gyms/{gid}")
    check("Public: get gym by ID", r)

    # Get by slug
    if slug:
        r = c.get(f"{BASE}/gyms/slug/{slug}")
        check("Public: get gym by slug", r)

    # Plans, Hours, Facilities
    r = c.get(f"{BASE}/gyms/{gid}/plans")
    check("Public: gym plans", r)

    r = c.get(f"{BASE}/gyms/{gid}/hours")
    check("Public: gym hours", r)

    r = c.get(f"{BASE}/gyms/{gid}/facilities")
    check("Public: gym facilities", r)

    # Reviews (empty initially)
    r = c.get(f"{BASE}/gyms/{gid}/reviews")
    check("Public: gym reviews", r)

    r = c.get(f"{BASE}/gyms/{gid}/reviews/summary")
    check("Public: reviews summary", r)


# ─── 9. CHATBOT FLOW (no login) ───────────────────────────────────────────────

def test_chatbot_flow(c: httpx.Client):
    section("9. PUBLIC CHATBOT — No Login Required")
    gid = state.get("gym_id")
    session_id = str(uuid.uuid4())
    state["chat_session_id"] = session_id

    messages = [
        "Hi, what are your timings?",
        "What membership plans do you have?",
        "Do you have parking?",
        "I'm interested in joining. What do I do next?",
    ]

    for msg in messages:
        r = c.post(f"{BASE}/chatbot/message", json={
            "gym_id": gid,
            "session_id": session_id,
            "message": msg
        })
        body = check(f"Chat: '{msg[:40]}...' " if len(msg) > 40 else f"Chat: '{msg}'", r)
        if body:
            reply = body["data"]["reply"]
            print(f"      Bot: {reply[:80]}{'...' if len(reply) > 80 else ''}")

    # Get conversation history
    r = c.get(f"{BASE}/chatbot/conversation/{session_id}", params={"gym_id": gid})
    body = check("Get conversation history", r)
    if body:
        turns = len(body["data"]["history"])
        print(f"      History: {turns} messages stored")

    # Lead capture (after bot got user's details)
    r = c.post(f"{BASE}/chatbot/lead-capture", json={
        "gym_id": gid,
        "lead_name": "Priya Verma",
        "phone": "+919876543210",
        "email": "priya@example.com",
        "initial_query": "Interested in monthly membership",
        "chat_transcript": [
            {"role": "user", "content": "Hi, what are your timings?"},
            {"role": "assistant", "content": "We are open 6 AM to 10 PM, Mon-Sat!"}
        ],
        "interested_services": {"membership": True, "personal_training": False},
        "budget_range": "1000-2000",
        "preferred_timing": "MORNING",
        "fitness_goals": {"weight_loss": True},
        "utm_source": "google",
        "utm_medium": "organic",
        "lead_source": "CHATBOT"
    })
    body = check("Lead capture from chatbot", r, 201)
    if body:
        state["lead_id"] = body["data"]["id"]
        print(f"      Lead ID: {state['lead_id']}")

    # Second lead for more tests
    r = c.post(f"{BASE}/chatbot/lead-capture", json={
        "gym_id": gid,
        "lead_name": "Amit Patel",
        "phone": "+919123456789",
        "initial_query": "Looking for personal training",
        "lead_source": "CHATBOT"
    })
    body = check("Second lead capture", r, 201)
    if body:
        state["lead_id_2"] = body["data"]["id"]


# ─── 10. GYM OWNER — CRM / LEADS ─────────────────────────────────────────────

def test_leads_crm(c: httpx.Client):
    section("10. GYM OWNER — Lead CRM")
    h = auth_header(state["owner_token"])
    gid = state["gym_id"]
    lead_id = state.get("lead_id")

    if not lead_id:
        print("  ⚠️  No lead captured — skipping")
        return

    # List leads
    r = c.get(f"{BASE}/gyms/{gid}/leads/", headers=h)
    body = check("List gym leads", r)
    if body:
        print(f"      Total leads: {body['data']['pagination']['total']}")

    # Filter by status
    r = c.get(f"{BASE}/gyms/{gid}/leads/", headers=h, params={"status": "NEW"})
    check("Filter leads by status=NEW", r)

    # Lead stats
    r = c.get(f"{BASE}/gyms/{gid}/leads/stats", headers=h)
    check("Lead dashboard stats", r)

    # Get single lead
    r = c.get(f"{BASE}/gyms/{gid}/leads/{lead_id}", headers=h)
    check("Get lead detail", r)

    # Update lead (move pipeline stage)
    r = c.patch(f"{BASE}/gyms/{gid}/leads/{lead_id}", headers=h, json={
        "status": "CONTACTED",
        "priority": "HIGH",
        "follow_up_notes": "Called and she is very interested. Scheduled a visit."
    })
    check("Update lead — mark CONTACTED", r)

    # Add interaction log
    r = c.post(f"{BASE}/gyms/{gid}/leads/{lead_id}/interactions", headers=h, json={
        "interaction_type": "CALL",
        "subject": "Initial Call",
        "content": "Called Priya. She is interested in the monthly plan. Will visit tomorrow.",
        "outcome": "POSITIVE",
        "next_action": "VISIT",
        "next_action_date": "2026-06-05"
    })
    check("Log call interaction", r, 201)

    r = c.post(f"{BASE}/gyms/{gid}/leads/{lead_id}/interactions", headers=h, json={
        "interaction_type": "WHATSAPP",
        "content": "Sent location and timings via WhatsApp.",
        "outcome": "SENT"
    })
    check("Log WhatsApp interaction", r, 201)

    # Get interactions
    r = c.get(f"{BASE}/gyms/{gid}/leads/{lead_id}/interactions", headers=h)
    body = check("Get lead interactions", r)
    if body:
        print(f"      Interactions logged: {len(body['data'])}")

    # Update status to INTERESTED
    r = c.patch(f"{BASE}/gyms/{gid}/leads/{lead_id}/status", headers=h, params={"status": "INTERESTED"})
    check("Lead status → INTERESTED", r)


# ─── 11. GYM OWNER — ADD MEMBERS ─────────────────────────────────────────────

def test_members(c: httpx.Client):
    section("11. GYM OWNER — Member Management")
    h = auth_header(state["owner_token"])
    gid = state["gym_id"]

    # Add member (Priya from lead)
    r = c.post(f"{BASE}/gyms/{gid}/members/", headers=h, json={
        "member_name": "Priya Verma",
        "phone": "+919876543210",
        "email": "priya@example.com",
        "date_of_birth": "1995-03-15",
        "gender": "FEMALE",
        "height_cm": 163,
        "weight_kg": 62.5,
        "fitness_goals": {"weight_loss": True, "endurance": True},
        "referral_source": "CHATBOT",
        "preferred_workout_time": "MORNING",
        "whatsapp_notifications": True,
        "email_notifications": True,
        "tags": ["lead-converted", "chatbot"],
        "notes": "Converted from chatbot lead"
    })
    body = check("Add member (Priya)", r, 201)
    if body:
        state["member_id"] = body["data"]["id"]
        state["member_code"] = body["data"].get("member_code")
        print(f"      Member ID: {state['member_id']}  Code: {state['member_code']}")

    # Add second member
    r = c.post(f"{BASE}/gyms/{gid}/members/", headers=h, json={
        "member_name": "Raj Kumar",
        "phone": "+919000011111",
        "gender": "MALE",
        "whatsapp_notifications": True,
    })
    body = check("Add member (Raj)", r, 201)
    if body:
        state["member_id_2"] = body["data"]["id"]

    # List members
    r = c.get(f"{BASE}/gyms/{gid}/members/", headers=h)
    body = check("List members", r)
    if body:
        print(f"      Total members: {body['data']['pagination']['total']}")

    # Search members
    r = c.get(f"{BASE}/gyms/{gid}/members/", headers=h, params={"search": "Priya"})
    check("Search member by name", r)

    # Get single member
    mid = state.get("member_id")
    if mid:
        r = c.get(f"{BASE}/gyms/{gid}/members/{mid}", headers=h)
        check("Get member detail", r)

        # Update member
        r = c.put(f"{BASE}/gyms/{gid}/members/{mid}", headers=h, json={
            "notes": "Joined after chatbot inquiry. Prefers morning sessions.",
            "tags": ["morning", "weight-loss", "chatbot-lead"]
        })
        check("Update member notes/tags", r)

        # Add membership
        r = c.post(f"{BASE}/gyms/{gid}/members/{mid}/memberships", headers=h, json={
            "plan_id": state["plan_id"],
            "start_date": "2026-06-02",
            "end_date": "2026-07-02",
            "plan_price": 1299,
            "discount_applied": 0,
            "total_amount": 1299,
            "payment_method": "UPI",
            "payment_status": "PAID",
            "payment_date": "2026-06-02"
        })
        check("Add membership to member", r, 201)

    # Member stats
    r = c.get(f"{BASE}/gyms/{gid}/members/stats", headers=h)
    body = check("Member dashboard stats", r)
    if body:
        stats = body["data"]
        print(f"      Active: {stats.get('active_members')}  Total: {stats.get('total_members')}")

    # Convert lead to member
    if state.get("lead_id") and state.get("member_id"):
        r = c.post(
            f"{BASE}/gyms/{gid}/leads/{state['lead_id']}/convert",
            headers=h,
            params={"member_id": state["member_id"]}
        )
        check("Convert lead → member", r)


# ─── 12. CHECK-INS ────────────────────────────────────────────────────────────

def test_checkins(c: httpx.Client):
    section("12. CHECK-INS")
    h = auth_header(state["owner_token"])
    gid = state["gym_id"]
    mid = state.get("member_id")

    if not mid:
        print("  ⚠️  No member — skipping")
        return

    # Check in
    r = c.post(f"{BASE}/checkins", headers=h, json={
        "member_id": mid,
        "gym_id": gid,
        "visit_type": "REGULAR",
        "purpose": "Cardio + Weights",
        "entry_method": "MANUAL",
        "facilities_used": ["Treadmills", "Free Weights"]
    })
    body = check("Member check-in", r, 201)
    if body:
        state["visit_id"] = body["data"]["id"]
        print(f"      Visit ID: {state['visit_id']}")

    # Double check-in should fail
    r = c.post(f"{BASE}/checkins", headers=h, json={
        "member_id": mid,
        "gym_id": gid,
        "visit_type": "REGULAR",
        "entry_method": "MANUAL"
    })
    blocked = r.status_code in (400, 409, 422)
    results.append(("Double check-in blocked", blocked, f"HTTP {r.status_code}"))
    print(f"  {'✅' if blocked else '❌'} Double check-in blocked → HTTP {r.status_code}")

    # Today's count
    r = c.get(f"{BASE}/gyms/{gid}/checkins/today-count", headers=h)
    body = check("Today's check-in count", r)
    if body:
        print(f"      Today check-ins: {body['data']['today_checkins']}")

    # List gym check-ins
    r = c.get(f"{BASE}/gyms/{gid}/checkins", headers=h)
    check("List gym check-ins (today)", r)

    # Member visit history
    r = c.get(f"{BASE}/gyms/{gid}/members/{mid}/visits", headers=h)
    check("Member visit history", r)

    # Check out
    if state.get("visit_id"):
        r = c.post(f"{BASE}/checkins/checkout", headers=h, json={
            "visit_id": state["visit_id"],
            "gym_id": gid
        })
        check("Member check-out", r)

    # Check in again (after checkout)
    r = c.post(f"{BASE}/checkins", headers=h, json={
        "member_id": mid,
        "gym_id": gid,
        "entry_method": "MANUAL"
    })
    body = check("Re-check-in after checkout", r, 201)
    if body:
        state["visit_id_2"] = body["data"]["id"]


# ─── 13. GYM OWNER DASHBOARD & ANALYTICS ─────────────────────────────────────

def test_dashboard_analytics(c: httpx.Client):
    section("13. GYM OWNER — Dashboard & Analytics")
    h = auth_header(state["owner_token"])
    gid = state["gym_id"]

    r = c.get(f"{BASE}/gyms/{gid}/dashboard", headers=h)
    body = check("Dashboard stats", r)
    if body:
        d = body["data"]
        print(f"      Active members: {d.get('active_members')}  "
              f"Leads this month: {d.get('leads_this_month')}  "
              f"Check-ins today: {d.get('checkins_today')}")

    r = c.get(f"{BASE}/gyms/{gid}/analytics/growth", headers=h, params={"months": 6})
    check("Member growth chart (6 months)", r)

    r = c.get(f"{BASE}/gyms/{gid}/analytics/revenue", headers=h, params={"months": 3})
    check("Revenue chart (3 months)", r)

    r = c.get(f"{BASE}/gyms/{gid}/analytics/funnel", headers=h)
    check("Lead funnel", r)

    r = c.get(f"{BASE}/gyms/{gid}/subscription", headers=h)
    check("Gym subscription status", r)


# ─── 14. GYM MANAGER (STAFF) ──────────────────────────────────────────────────

def test_gym_manager(c: httpx.Client):
    section("14. GYM MANAGER — Invite & Access")
    h_owner = auth_header(state["owner_token"])
    gid = state["gym_id"]

    # Register a manager user first
    uid = str(uuid.uuid4())[:8]
    email = f"manager_{uid}@gmail.com"
    r = c.post(f"{BASE}/auth/register", json={
        "full_name": "Sneha Manager",
        "email": email,
        "password": "Manager@1234",
        "role": "GYM_MANAGER"
    })
    check("Register manager user", r, 201)

    # Login as manager
    r = c.post(f"{BASE}/auth/login", json={"email": email, "password": "Manager@1234"})
    body = check("Manager login", r)
    if body:
        state["manager_token"] = body["data"]["access_token"]

    # List staff (only owner)
    r = c.get(f"{BASE}/gyms/{gid}/staff", headers=h_owner)
    body = check("Owner: list gym staff", r)
    if body:
        print(f"      Current staff: {len(body['data'])} member(s)")

    # Owner invites manager
    r = c.post(f"{BASE}/gyms/{gid}/staff", headers=h_owner, json={
        "email": email,
        "role": "GYM_MANAGER",
        "employment_type": "FULL_TIME"
    })
    check("Owner: add manager to gym", r, 201)

    # Manager can now access gym data
    if state.get("manager_token"):
        h_mgr = auth_header(state["manager_token"])

        r = c.get(f"{BASE}/gyms/{gid}/members/", headers=h_mgr)
        check("Manager: list members", r)

        r = c.get(f"{BASE}/gyms/{gid}/leads/", headers=h_mgr)
        check("Manager: list leads", r)

        r = c.get(f"{BASE}/gyms/{gid}/checkins", headers=h_mgr)
        check("Manager: list check-ins", r)

        # Manager CANNOT add staff (not owner)
        r = c.post(f"{BASE}/gyms/{gid}/staff", headers=h_mgr, json={
            "email": "random@gmail.com",
            "role": "GYM_MANAGER"
        })
        blocked = r.status_code in (403, 404)
        results.append(("Manager blocked from adding staff", blocked, f"HTTP {r.status_code}"))
        print(f"  {'✅' if blocked else '❌'} Manager blocked from adding staff → HTTP {r.status_code}")

    # Update permissions
    if state.get("manager_token"):
        r = c.get(f"{BASE}/auth/me", headers=auth_header(state["manager_token"]))
        body = r.json()
        if body.get("data"):
            mgr_user_id = body["data"]["id"]
            r = c.patch(f"{BASE}/gyms/{gid}/staff/{mgr_user_id}/permissions",
                       headers=h_owner,
                       json={"permissions": {"view_members": True, "manage_members": True,
                                              "view_leads": True, "manage_leads": False}})
            check("Owner: update manager permissions", r)


# ─── 15. REVIEWS ──────────────────────────────────────────────────────────────

def test_reviews(c: httpx.Client):
    section("15. REVIEWS")
    h_owner = auth_header(state["owner_token"])
    gid = state["gym_id"]

    # Submit review (as gym owner — in real life it would be a member/visitor)
    r = c.post(f"{BASE}/reviews", headers=h_owner, json={
        "gym_id": gid,
        "rating": 5,
        "review_title": "Amazing gym!",
        "review_content": "Great equipment, clean facilities, friendly staff. Highly recommend!",
        "review_type": "GENERAL"
    })
    body = check("Submit review (pending moderation)", r, 201)
    if body:
        state["review_id"] = body["data"]["id"]
        print(f"      Review ID: {state['review_id']} — Status: {body['data']['status']}")

    # Admin approve the review
    h_admin = auth_header(state["super_token"])
    if state.get("review_id"):
        r = c.patch(f"{BASE}/admin/reviews/{state['review_id']}/moderate",
                   headers=h_admin,
                   json={"status": "APPROVED", "moderation_notes": "Verified genuine review"})
        check("Admin: approve review", r)

    # Public: see approved reviews
    r = c.get(f"{BASE}/gyms/{gid}/reviews")
    body = check("Public: approved reviews", r)
    if body:
        print(f"      Approved reviews: {body['data']['pagination']['total']}")

    # Rating summary
    r = c.get(f"{BASE}/gyms/{gid}/reviews/summary")
    body = check("Rating summary", r)
    if body:
        print(f"      Avg rating: {body['data']['average_rating']}  Total: {body['data']['total_reviews']}")

    # Owner responds to review
    if state.get("review_id"):
        r = c.post(f"{BASE}/reviews/{state['review_id']}/respond", headers=h_owner, json={
            "response_content": "Thank you so much! We work hard to maintain quality. See you soon! 💪"
        })
        check("Owner: respond to review", r)

    # Vote on review
    if state.get("review_id"):
        r = c.post(f"{BASE}/gyms/{gid}/reviews/vote/{state['review_id']}", params={"helpful": True})
        check("Vote review as helpful", r)


# ─── 16. SUBSCRIPTIONS ────────────────────────────────────────────────────────

def test_subscriptions(c: httpx.Client):
    section("16. SUBSCRIPTIONS")
    h_owner = auth_header(state["owner_token"])

    # List plans (public)
    r = c.get(f"{BASE}/subscriptions/plans")
    body = check("List subscription plans", r)
    if body:
        plans = body["data"]
        print(f"      Available plans: {len(plans)}")
        for p in plans:
            print(f"        - {p['plan_name']}: ₹{p['base_price']}/mo")
        if plans:
            state["sub_plan_id"] = plans[0]["id"]  # free plan

    # Subscribe to free plan
    if state.get("sub_plan_id"):
        r = c.post(f"{BASE}/subscriptions/subscribe", headers=h_owner, json={
            "plan_id": state["sub_plan_id"],
            "gym_id": state["gym_id"]
        })
        body = check("Subscribe to free plan", r, 201)
        if body:
            state["sub_id"] = body["data"]["id"]
            print(f"      Subscription ID: {state['sub_id']}  Status: {body['data']['status']}")

    # Get my subscription
    r = c.get(f"{BASE}/subscriptions/my", headers=h_owner, params={"gym_id": state["gym_id"]})
    check("Get my subscription", r)

    # Payment history
    r = c.get(f"{BASE}/subscriptions/my/payments", headers=h_owner)
    check("Payment history", r)

    # Specific plan detail
    if state.get("sub_plan_id"):
        r = c.get(f"{BASE}/subscriptions/plans/{state['sub_plan_id']}")
        check("Get plan detail", r)


# ─── 17. NOTIFICATIONS ────────────────────────────────────────────────────────

def test_notifications(c: httpx.Client):
    section("17. NOTIFICATIONS")
    h = auth_header(state["owner_token"])

    r = c.get(f"{BASE}/notifications/", headers=h)
    body = check("List notifications", r)
    if body:
        print(f"      Total notifications: {body['data']['pagination']['total']}")

    r = c.get(f"{BASE}/notifications/unread-count", headers=h)
    body = check("Unread count", r)
    if body:
        print(f"      Unread: {body['data']['unread_count']}")

    r = c.post(f"{BASE}/notifications/mark-read", headers=h)
    check("Mark all read", r)

    r = c.get(f"{BASE}/notifications/unread-count", headers=h)
    body = check("Unread count after mark-all-read", r)
    if body:
        ok = body["data"]["unread_count"] == 0
        results.append(("Unread = 0 after mark all", ok, str(body["data"]["unread_count"])))
        print(f"  {'✅' if ok else '❌'} Unread after mark-all = {body['data']['unread_count']}")


# ─── 18. BULK WHATSAPP ────────────────────────────────────────────────────────

def test_bulk_whatsapp(c: httpx.Client):
    section("18. BULK WHATSAPP")
    h = auth_header(state["owner_token"])
    gid = state["gym_id"]

    r = c.post(f"{BASE}/gyms/{gid}/members/bulk-whatsapp", headers=h, json={
        "message": "🎉 Special offer! Renew your membership this week and get 10% off! 💪",
        "member_ids": None  # all members
    })
    body = check("Bulk WhatsApp (all members)", r)
    if body:
        d = body["data"]
        print(f"      Sent: {d.get('sent')}  Failed: {d.get('failed')}")

    # Send expiry reminders
    r = c.post(f"{BASE}/gyms/{gid}/members/send-expiry-reminders", headers=h)
    body = check("Send expiry reminders", r)
    if body:
        print(f"      Expiring: {body['data']['total_expiring']}  Sent: {body['data']['reminders_sent']}")


# ─── 19. ACCESS CONTROL CHECKS ────────────────────────────────────────────────

def test_access_control(c: httpx.Client):
    section("19. ACCESS CONTROL — Permission Boundaries")
    gid = state["gym_id"]
    h_owner = auth_header(state["owner_token"])

    # Public cannot access protected routes (401 = unauthenticated, 403 = forbidden — both are correct blocks)
    r = c.get(f"{BASE}/gyms/{gid}/members/")
    blocked = r.status_code in (401, 403)
    results.append(("Public blocked from member list", blocked, f"HTTP {r.status_code}"))
    print(f"  {'✅' if blocked else '❌'} Public blocked from member list → HTTP {r.status_code}")

    r = c.get(f"{BASE}/gyms/{gid}/leads/")
    blocked = r.status_code in (401, 403)
    results.append(("Public blocked from leads", blocked, f"HTTP {r.status_code}"))
    print(f"  {'✅' if blocked else '❌'} Public blocked from leads → HTTP {r.status_code}")

    # Owner cannot access admin routes
    r = c.get(f"{BASE}/admin/stats", headers=h_owner)
    blocked = r.status_code == 403
    results.append(("GYM_OWNER blocked from /admin/stats", blocked, f"HTTP {r.status_code}"))
    print(f"  {'✅' if blocked else '❌'} GYM_OWNER blocked from /admin/stats → HTTP {r.status_code}")

    # Owner cannot approve their own gym (old route in gyms - not admin route)
    r = c.post(f"{BASE}/gyms/{gid}/approve", headers=h_owner)
    blocked = r.status_code == 403
    results.append(("GYM_OWNER blocked from self-approving", blocked, f"HTTP {r.status_code}"))
    print(f"  {'✅' if blocked else '❌'} GYM_OWNER blocked from gym self-approval → HTTP {r.status_code}")

    # Admin cannot be blocked from stats
    h_admin = auth_header(state["super_token"])
    r = c.get(f"{BASE}/admin/stats", headers=h_admin)
    ok = r.status_code == 200
    results.append(("SUPER_ADMIN can access /admin/stats", ok, f"HTTP {r.status_code}"))
    print(f"  {'✅' if ok else '❌'} SUPER_ADMIN can access /admin/stats → HTTP {r.status_code}")

    # Bad token rejected
    r = c.get(f"{BASE}/auth/me", headers={"Authorization": "Bearer badtoken123"})
    blocked = r.status_code == 401
    results.append(("Bad token → 401", blocked, f"HTTP {r.status_code}"))
    print(f"  {'✅' if blocked else '❌'} Bad token rejected → HTTP {r.status_code}")


# ─── 20. ADMIN USER MANAGEMENT ────────────────────────────────────────────────

def test_admin_user_management(c: httpx.Client):
    section("20. SUPER ADMIN — User Management")
    h = auth_header(state["super_token"])

    # Get admin user
    if state.get("admin_user_id"):
        uid = state["admin_user_id"]
        r = c.get(f"{BASE}/admin/users/{uid}", headers=h)
        check("Get user detail", r)

        r = c.patch(f"{BASE}/admin/users/{uid}/deactivate", headers=h)
        check("Deactivate user", r)

        r = c.patch(f"{BASE}/admin/users/{uid}/activate", headers=h)
        check("Re-activate user", r)

        r = c.patch(f"{BASE}/admin/users/{uid}/unlock", headers=h)
        check("Unlock user account", r)

    # System settings
    r = c.get(f"{BASE}/admin/settings", headers=h)
    body = check("Get system settings", r)
    if body and body["data"]:
        key = body["data"][0]["setting_key"]
        r = c.put(f"{BASE}/admin/settings/{key}", headers=h, json={"value": body["data"][0]["setting_value"]})
        check(f"Update system setting ({key})", r)


# ─── SUMMARY ──────────────────────────────────────────────────────────────────

def print_summary():
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed

    print(f"\n{'═' * 60}")
    print(f"  RESULTS: {passed}/{total} passed  ({failed} failed)")
    print(f"{'═' * 60}")

    if failed:
        print("\n  FAILURES:")
        for label, ok, info in results:
            if not ok:
                print(f"    {FAIL} {label}  ({info})")

    print(f"\n  {'🎉 All tests passed!' if failed == 0 else f'⚠️  {failed} test(s) need attention.'}")
    print()
    return failed == 0


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'═' * 60}")
    print("  GymConnect AI — Full Flow Test Suite")
    print(f"  Base URL: {BASE}")
    print(f"{'═' * 60}")

    with httpx.Client(timeout=30) as c:
        test_health(c)
        test_super_admin_login(c)
        test_admin_account(c)
        test_super_admin_operations(c)
        test_gym_owner_flow(c)
        test_admin_approve_gym(c)
        test_gym_setup(c)
        test_public_gym_page(c)
        test_chatbot_flow(c)
        test_leads_crm(c)
        test_members(c)
        test_checkins(c)
        test_dashboard_analytics(c)
        test_gym_manager(c)
        test_reviews(c)
        test_subscriptions(c)
        test_notifications(c)
        test_bulk_whatsapp(c)
        test_access_control(c)
        test_admin_user_management(c)

    passed = print_summary()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
