# 🎫 Ticketing AI

> Manage your entire task backlog through natural conversation. No forms, no clicks — just talk.

Ticketing AI is a full-stack conversational ticketing system that lets you create tickets, manage users, and run projects entirely through natural language. Backed by a production-grade FastAPI + PostgreSQL + Redis stack, with a LangGraph agent that remembers context across your session.

---

## ✨ What It Does

| Say this… | And it does this |
|---|---|
| *"Create a ticket for the login bug"* | Asks for missing details one field at a time |
| *"What projects are available?"* | Shows them — then resumes the ticket creation |
| *"Set the due date to June 30"* | Knows which ticket you mean — no ID needed |
| *"Show me all users"* | Lists everyone with name, email, and role |
| *"Create a user named Alice"* | Asks for her email, then creates her |

The agent never forgets what you were doing. Switch topics mid-task, look something up, come back — it keeps your place.

---

## 🏗️ Architecture

```
Browser (chatbot.html)
        │  HTTP
        ▼
FastAPI  (uvicorn app.main:app)
        │
        ├── /api/v1/chat   ◄── LangGraph Agent
        │                         ├── classify_intent   (Groq LLM)
        │                         ├── extract_slots     (Groq LLM)
        │                         ├── check_slots
        │                         └── execute_tool
        │
        ├── /api/v1/tickets
        ├── /api/v1/users
        ├── /api/v1/projects
        └── /api/v1/reports
                │
                ├── PostgreSQL 15  (data store, port 5433)
                └── Redis 7        (session memory, port 6379)
```

**Tech stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 (async) · Alembic · asyncpg · Redis · LangGraph · Groq (`openai/gpt-oss-120b`) · Pydantic v2

---

## 📋 Prerequisites

Before you start, make sure you have these installed:

| Tool | Version | Check |
|---|---|---|
| Python | 3.11+ | `python --version` |
| Docker Desktop | Latest | `docker --version` |
| Git | Any | `git --version` |

You also need a **free Groq API key** — get one in 30 seconds at [console.groq.com](https://console.groq.com).

---

## 🚀 Local Setup — Step by Step

### Step 1 — Clone the repo

```bash
git clone https://github.com/your-username/ticketing-ai.git
cd ticketing-ai
```

### Step 2 — Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
pip install aiofiles   # needed for FastAPI static file serving
```

### Step 4 — Create your `.env` file

```bash
cp .env.example .env
```

Now open `.env` and fill in your values:

```bash
# .env

APP_NAME=ticketing-ai
APP_ENV=development

# PostgreSQL — matches docker-compose.yml exactly, don't change unless you know why
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/ticketing

# Redis — matches docker-compose.yml
REDIS_URL=redis://localhost:6379/0

# Your Groq API key — get it free at https://console.groq.com
GROQ_API_KEY=gsk_your_key_here
```

> ⚠️ Never commit your `.env` file. It's already in `.gitignore`.

### Step 5 — Start PostgreSQL and Redis

```bash
docker compose up -d
```

Verify both containers are running:

```bash
docker compose ps
```

You should see:

```
NAME                 STATUS
ticketing_postgres   running
ticketing_redis      running
```

### Step 6 — Run the database migrations

This creates all the tables. Only needed once (or after a reset):

```bash
alembic upgrade head
```

Expected output ends with something like:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 242344ec059f, initial_schema
```

### Step 7 — Set up the frontend

Create the `frontend/` folder and move the chatbot into it:

```bash
mkdir frontend
cp chatbot.html frontend/index.html
```

### Step 8 — Start the server

```bash
uvicorn app.main:app --reload
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Step 9 — Open the chatbot

Go to **[http://localhost:8000](http://localhost:8000)** in your browser.

1. The API URL field already says `http://localhost:8000` — leave it
2. Click **Connect**
3. Start chatting

---

## 💬 Usage Examples

```
You:  Create a ticket for the login bug
Bot:  What should the ticket title be?

You:  Fix broken OAuth redirect
Bot:  Which project should this belong to? (or ask me to show you available projects)

You:  Show me available projects
Bot:  Here are the available projects — pick one:
      • Backend API  (active)
      • Mobile App   (active)
      (Still working on create ticket — just pick one above.)

You:  Backend API
Bot:  Got it! Your ticket "Fix broken OAuth redirect" has been created
      in Backend API with medium priority.

You:  Set the due date to July 15
Bot:  Done! I've set the due date on "Fix broken OAuth redirect" to July 15.
```

---

## 📁 Project Structure

```
ticketing-ai/
├── app/
│   ├── main.py                  # FastAPI app, static file serving
│   ├── config.py                # Settings from .env
│   ├── database.py              # Async SQLAlchemy engine
│   ├── redis_client.py          # Async Redis client
│   │
│   ├── agent/                   # LangGraph conversational AI
│   │   ├── graph.py             # State graph + routing logic
│   │   ├── session_manager.py   # Redis session CRUD
│   │   ├── llm.py               # Groq API client
│   │   ├── state.py             # AgentState TypedDict
│   │   └── nodes/
│   │       ├── classify_intent.py   # What does the user want?
│   │       ├── extract_slots.py     # What info did they give?
│   │       ├── check_slots.py       # What's still missing?
│   │       └── execute_tool.py      # Do the thing
│   │
│   ├── api/                     # REST endpoints
│   │   ├── chat.py              # POST /api/v1/chat/
│   │   ├── tickets.py
│   │   ├── users.py
│   │   ├── projects.py
│   │   └── reports.py
│   │
│   ├── models/                  # SQLAlchemy ORM models
│   ├── repositories/            # Database access layer
│   ├── services/                # Business logic
│   └── schemas/                 # Pydantic request/response models
│
├── alembic/                     # Database migrations
│   └── versions/
│       └── 242344ec059f_initial_schema.py
│
├── frontend/
│   └── index.html               # Chat UI (served at /)
│
├── docker-compose.yml           # PostgreSQL + Redis
├── requirements.txt
├── .env.example                 # Template — copy to .env
└── alembic.ini
```

---

## 🔌 API Reference

The full interactive docs are at **[http://localhost:8000/docs](http://localhost:8000/docs)** when the server is running.

### Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chat/session` | Create a new conversation session |
| `POST` | `/api/v1/chat/` | Send a message, get a response |
| `GET` | `/api/v1/chat/session/{id}` | Inspect session state |
| `DELETE` | `/api/v1/chat/session/{id}` | Clear a session |

### Tickets

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/tickets` | Create ticket |
| `GET` | `/api/v1/tickets` | List tickets |
| `GET` | `/api/v1/tickets/{id}` | Get ticket |
| `PATCH` | `/api/v1/tickets/{id}` | Update ticket |

### Users, Projects, Reports — same pattern. See `/docs`.

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_NAME` | ✅ | Application name |
| `APP_ENV` | ✅ | `development` or `production` |
| `DATABASE_URL` | ✅ | PostgreSQL connection string (asyncpg driver) |
| `REDIS_URL` | ✅ | Redis connection string |
| `GROQ_API_KEY` | ✅ | From [console.groq.com](https://console.groq.com) |

---

## 🧯 Troubleshooting

**`[Errno 61] Connect call failed ('127.0.0.1', 5433)`**
PostgreSQL isn't running. Run `docker compose up -d` and try again.

**`groq.BadRequestError: model_decommissioned`**
Groq retired the model. Open `app/agent/llm.py`, update `PRIMARY_MODEL` to a current model from [console.groq.com/docs/deprecations](https://console.groq.com/docs/deprecations).

**`Session not found`**
Your session expired (7-day TTL) or Redis restarted. Click **New session** in the chat UI.

**`alembic upgrade head` fails with connection error**
The database container isn't ready yet. Wait 5 seconds and try again, or check `docker compose ps`.

**Port 5433 already in use**
Another PostgreSQL instance is running. Either stop it (`pg_ctl stop`) or change the port in `docker-compose.yml` and `DATABASE_URL` in `.env` to match.

---

## 🔄 Resetting Everything

To wipe the database and start fresh:

```bash
docker compose down -v    # removes containers AND volumes (all data)
docker compose up -d      # fresh start
alembic upgrade head      # recreate tables
```

---

## 🤝 Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run the tests: `pytest`
5. Open a pull request

---

## 📄 License

MIT