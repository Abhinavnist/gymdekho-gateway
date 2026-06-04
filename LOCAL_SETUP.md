# GymConnect AI — Local Development Setup

## Prerequisites

- Python 3.11+ installed
- Docker Desktop installed and running
- Git

---

## Step 1: Clone & Navigate

```bash
cd /Users/pop/Desktop/gymconnect-ai/backend
```

---

## Step 2: Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows
```

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4: Setup Environment Variables

```bash
cp .env.example .env
```

Open `.env` and update only what you need locally:

```env
# These are already set correctly for local Docker setup:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=gymconnect_ai
DB_USER=gymconnect_user
DB_PASSWORD=gymconnect_pass

# Change this — must be a long random string:
JWT_SECRET_KEY=your_super_secret_key_here_make_it_long

# Add your OpenAI key to enable chatbot:
OPENAI_API_KEY=sk-...

# Leave Twilio/SendGrid/Cloudinary/Razorpay blank for now
# The app will still run — those features will just log warnings
```

---

## Step 5: Start PostgreSQL via Docker

```bash
docker compose up -d
```

This starts a PostgreSQL 16 container on port 5432.

Verify it's running:
```bash
docker ps
# You should see: gymconnect_postgres
```

Check logs if something's wrong:
```bash
docker compose logs postgres
```

---

## Step 6: Run Database Migrations

```bash
python scripts/run_migrations.py
```

Expected output:
```
Applying 001_initial_schema.sql...
  ✅ 001_initial_schema.sql applied.

✅ All migrations complete.
```

Verify the tables were created:
```bash
docker exec -it gymconnect_postgres psql -U gymconnect_user -d gymconnect_ai -c "\dt"
```

---

## Step 7: Start the FastAPI Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Starting GymConnect AI [development]
INFO:     Database connection pool created.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 8: Verify Everything Works

Open your browser:

- **API Docs (Swagger)**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health
- **ReDoc**: http://localhost:8000/redoc

Health check should return:
```json
{"status": "ok", "app": "GymConnect AI", "env": "development"}
```

---

## Quick Test — Register a Gym Owner

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test Owner",
    "email": "owner@test.com",
    "password": "Password123",
    "role": "GYM_OWNER",
    "city": "Mumbai",
    "state": "Maharashtra"
  }'
```

Then login:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "owner@test.com", "password": "Password123"}'
```

Copy the `access_token` from the response and use it in the Authorization header for protected routes.

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                     # FastAPI entry point
│   ├── config.py                   # All settings from .env
│   ├── api/v1/                     # Route handlers (thin layer)
│   │   ├── auth.py
│   │   ├── gyms.py
│   │   ├── members.py
│   │   ├── leads.py
│   │   └── chatbot.py
│   ├── services/                   # Business logic
│   │   ├── auth_service.py
│   │   ├── gym_service.py
│   │   ├── member_service.py
│   │   └── chatbot_service.py
│   ├── database/
│   │   ├── connection.py           # psycopg3 async pool
│   │   ├── migrations/             # SQL migration files
│   │   └── queries/                # Raw SQL queries per module
│   ├── models/                     # Pydantic request/response schemas
│   ├── core/                       # Auth, dependencies, exceptions
│   └── utils/                      # email, whatsapp, file upload, helpers
├── scripts/
│   └── run_migrations.py
├── docker-compose.yml              # PostgreSQL only
├── requirements.txt
├── .env.example
└── LOCAL_SETUP.md                  # This file
```

---

## Useful Commands

```bash
# Stop PostgreSQL
docker compose down

# Stop and delete all data (fresh start)
docker compose down -v

# Connect to DB directly
docker exec -it gymconnect_postgres psql -U gymconnect_user -d gymconnect_ai

# Check migration history
docker exec -it gymconnect_postgres psql -U gymconnect_user -d gymconnect_ai -c "SELECT * FROM schema_migrations;"

# View logs
docker compose logs -f postgres
```

---

## Common Issues

**Port 5432 already in use:**
```bash
# Find what's using it
lsof -i :5432
# Stop your local postgres if running
brew services stop postgresql
```

**Database connection refused:**
- Make sure Docker is running: `docker ps`
- Make sure container is healthy: `docker compose ps`

**Module not found errors:**
- Make sure venv is activated: `source venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`
