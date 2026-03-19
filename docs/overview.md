# KBTU Student Assistant Bot

A Telegram-based Retrieval-Augmented Generation (RAG) assistant for students of Kazakh-British Technical University (KBTU). The bot answers university-related questions by retrieving context from a PostgreSQL + pgvector knowledge base and generating responses via Groq LLM, while also providing access to university schedules scraped from the WSP portal.

## Tech Stack

- **Language:** Python 3.11+
- **Bot Framework:** aiogram 3.x (async Telegram Bot API)
- **Database:** PostgreSQL with pgvector extension (vector similarity search)
- **ORM:** SQLAlchemy 2.x (async, mapped columns)
- **LLM Provider:** Groq API (`llama-3.1-8b-instant`)
- **Embedding Model:** `intfloat/multilingual-e5-base` (768-dimensional, via sentence-transformers)
- **Admin Panel:** Streamlit
- **Schedule Scraper:** Playwright (headless Chromium)
- **Containerization:** Docker & Docker Compose
- **CI/CD:** GitHub Actions

## Key Features

- **RAG-powered Q&A** — answers student questions using vector-search retrieval from a curated knowledge base, with context injected into an LLM system prompt.
- **File Retrieval** — automatically indexes documents and photos posted in a linked Telegram channel (with hashtag-based categorization) and sends relevant files alongside AI answers.
- **University Schedule Search** — search class schedules by instructor, room, or subject. Schedule data is scraped from the WSP portal and stored in a normalized relational schema.
- **Free Room Finder** — real-time query for currently unoccupied classrooms, with time-shifting logic to account for inter-class breaks.
- **User Feedback (RLHF)** — inline 👍/👎 buttons on every AI response. Interaction logs with feedback scores are stored for analysis.
- **Daily Quota System** — per-user request limits with automatic 24-hour reset.
- **Anti-Spam Middleware** — TTL-based throttling to prevent message flooding.
- **Streamlit Admin Panel** — full CRUD for the knowledge base and files, user quota management, an RAG playground, schedule viewer, and an RLHF feedback dashboard.

## Project Structure

```
student-assistant-bot/
├── main.py                  # Bot entry point: DB init, router registration, polling
├── config.py                # Environment variable loader (BOT_TOKEN, DB, Groq, WSP)
├── admin.py                 # Streamlit admin panel (knowledge CRUD, files, users, RLHF, schedule)
├── requirements.txt         # Python dependencies (PyTorch CPU, aiogram, pgvector, etc.)
├── Dockerfile               # Multi-stage build: system deps → pip → model download → app code
├── docker-compose.yml       # Services: db (pgvector), bot, admin (Streamlit)
├── .env / example.env       # Environment variables template
│
├── bot/
│   ├── handlers/
│   │   ├── commands.py      # /start, help button
│   │   ├── ai.py            # Catch-all RAG handler (vector search → LLM → file sending)
│   │   ├── schedule.py      # /schedule command, FSM-based search (instructor/room/subject)
│   │   ├── files.py         # Channel file auto-indexing, category-based file sending
│   │   └── feedback.py      # Inline 👍/👎 callback handlers
│   ├── keyboards/
│   │   ├── __init__.py      # Main reply keyboard (schedule, free rooms, map, calendar, RUPs)
│   │   ├── schedule.py      # Inline keyboard for schedule search type selection
│   │   └── feedback.py      # Inline 👍/👎 keyboard factory
│   ├── middlewares/
│   │   └── throttling.py    # TTLCache-based anti-spam middleware
│   └── states/
│       └── schedule.py      # FSM states for schedule search flow
│
├── core/
│   ├── database.py          # Async SQLAlchemy engine & session factory (NullPool)
│   ├── models.py            # ORM models: KnowledgeItem, FileItem, User, InteractionLog
│   └── wsp_models.py        # ORM models: Subject, Instructor, Room, ScheduleEvent (+ enums)
│
├── services/
│   ├── embeddings.py        # Sentence-transformers model loader & get_vector() utility
│   ├── ai_service.py        # Groq LLM client: system prompt construction & completion
│   ├── repo.py              # Repository layer: knowledge/file CRUD, vector search, user/quota, RLHF
│   └── wsp_repo.py          # Schedule queries: by instructor/room/subject, free rooms algorithm
│
├── utils/
│   └── formatters.py        # Schedule & free-room output formatters (HTML & plain text)
│
├── wsp_scraper/
│   ├── main.py              # Scraper entry point: login → scroll → scrape → save pipeline
│   ├── browser.py           # Playwright automation: login, navigation, row/block extraction
│   ├── parser.py            # Schedule block text parser & validation rules
│   ├── schemas.py           # Dataclasses: ParsedBlock, SubjectEntry
│   ├── db_service.py        # Upsert logic for Subject/Instructor/Room/ScheduleEvent
│   └── audit.py             # Dropped-item audit logger (JSONL)
│
├── data/
│   └── faq.json             # Seed FAQ entries (Retake, Add/Drop, Military department)
│
└── .github/
    └── workflows/
        └── docker-test.yml  # CI: build & smoke-test Docker containers on push/PR to main
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/student-assistant-bot.git
cd student-assistant-bot
```

### 2. Configure Environment

Copy the example environment file and fill in the required values:

```bash
cp example.env .env
```

Edit `.env` with your credentials:

```dotenv
BOT_TOKEN=<your_telegram_bot_token>
GROQ_API_KEY=<your_groq_api_key>
CHANNEL_ID=<telegram_channel_id>

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=kbtu_db

DAILY_LIMIT=5
DB_HOST=localhost

WSP_LOGIN=<your_wsp_login>
WSP_PASSWORD=<your_wsp_password>
```

### 3. Build and Run

```bash
docker compose up -d --build
```

This starts three services:
- **db** — PostgreSQL with pgvector on port `5432`
- **bot** — the Telegram bot (polling mode)
- **admin** — Streamlit admin panel on port `8501`

### 4. Verify

```bash
docker compose ps
docker logs kbtu_rag_bot
```

Open the admin panel at `http://localhost:8501`.
