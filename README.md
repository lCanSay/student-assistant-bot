# KBTU Student Assistant Bot — «Асия»

A Telegram RAG bot that answers KBTU students' questions about academic life:
procedures (add/drop, retakes), services (dorms, military office, medical
centre), schedules, documents, and more. Built around a curated knowledge
base plus a strict vector-search pipeline that refuses to hallucinate.

The project ships with a Streamlit admin panel so you can manage content,
test retrieval, and inspect users without touching the database directly.

---

## What's in the box

| Component | What it does |
|---|---|
| **Telegram bot** ([main.py](main.py), [bot/handlers/](bot/handlers/)) | Aiogram-based bot. Catches user questions, runs RAG, sends answers + attachments. |
| **RAG pipeline** ([services/embeddings.py](services/embeddings.py), [bot/handlers/ai.py](bot/handlers/ai.py)) | Multilingual E5 embeddings (768-dim), cosine-distance search in PostgreSQL + pgvector, strict grounding via Groq LLM. |
| **File attachment system** ([services/repo.py](services/repo.py), [bot/handlers/files.py](bot/handlers/files.py)) | Two-path attachment: curated links (knowledge ↔ file) + strict vector fallback with keyword gating. |
| **Admin panel** ([admin.py](admin.py)) | Streamlit UI for knowledge/files/users management plus a retrieval playground showing distances, keyword hits, and filter decisions. |
| **WSP scraper** ([wsp_scraper/](wsp_scraper/)) | Logs into WSP to import course schedules into the DB. |
| **Feedback logging** ([bot/handlers/feedback.py](bot/handlers/feedback.py)) | 👍/👎 buttons attached to every answer; feedback stored in `interaction_logs`. |

---

## How RAG works here, in one picture

```
user question
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Embed (multilingual-e5-base, "query: " prefix)                │
└─────────────────────────────────────────────────────────────────┘
     │
     ├──► knowledge vector search (top-3, cosine dist ≤ 0.35)
     │        │
     │        ├── matches → build <knowledge> context
     │        │              → Groq LLM answers STRICTLY from it
     │        └── empty    → bot refuses (no LLM call, no quota spent)
     │
     └──► file vector search (top-5)
              │
              ├── CURATED path — files linked to a matched knowledge entry
              │   are always attached (no thresholds).
              │
              └── FALLBACK path — attaches at most 1 file that passes ALL:
                     1. a file keyword appears in the query (substring)
                     2. distance ≤ 0.20
                     3. gap ≥ 0.05 to the next keyword-matching file
```

The LLM system prompt forbids inventing information: if the retrieved
context doesn't cover the question, the bot says *"По этому вопросу у меня
нет данных. Обратитесь в деканат или Офис Регистратора."* See
[services/ai_service.py](services/ai_service.py) for the prompt and the
multi-model fallback chain.

---

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- A **Groq API key** — free tier at [console.groq.com](https://console.groq.com). Required for any AI answer.
- A **Telegram bot token** — only required if you actually want to run the bot in Telegram. Not needed for local admin-panel work.
- (Optional) **WSP credentials** — only required if you want to scrape schedules.

---

## Quick start — local setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd student-assistant-bot
cp example.env .env
```

Open `.env` and fill in:

```env
BOT_TOKEN=<your telegram bot token>   # optional for admin-only work
GROQ_API_KEY=<your groq api key>      # required for AI answers
CHANNEL_ID=<telegram channel id>      # optional; used by the file indexer

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=kbtu_db

DAILY_LIMIT=50                        # per-user AI request quota / 24h
DB_HOST=localhost                     # Docker overrides this to "db"

WSP_LOGIN=<wsp login>                 # optional, for schedule scraper
WSP_PASSWORD=<wsp password>           # optional
```

> **Note.** You only need a valid `BOT_TOKEN` to test the Telegram side.
> The admin panel and RAG playground work with just `GROQ_API_KEY`.

### 2. Start the services

```bash
docker compose up --build
```

This builds one image and launches three containers:

| Service | Container | Purpose |
|---|---|---|
| `db` | `kbtu_rag_db` | PostgreSQL 16 + pgvector (port `5432`) |
| `bot` | `kbtu_rag_bot` | Telegram bot polling loop |
| `admin` | `kbtu_rag_admin` | Streamlit admin panel (port `8501`) |

Both `bot` and `admin` mount the repo root as `/app` — edits to `.py` files
take effect on `docker compose restart bot` / `admin`, no rebuild needed.

### 3. Open the admin panel

<http://localhost:8501>

On first launch the bot creates all tables automatically (the migration
block in [main.py](main.py) runs `CREATE EXTENSION vector` and
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for every schema field).

---

## Admin panel — pages

### 📝 Knowledge Base

CRUD for the knowledge entries that the RAG system answers from.

Each entry has four fields: `title`, `content`, `category`, `keywords`. On
save, the admin panel regenerates the vector embedding automatically.

A multi-select **"Прикреплённые файлы"** lets you link files to a knowledge
entry — this is the **primary** file-attachment path and the most reliable
way to make sure a file reaches the user.

> **To write good entries that the vector search can actually find, read
> [docs/CONTENT_GUIDE_EN.md](docs/CONTENT_GUIDE_EN.md)** (or
> [docs/CONTENT_GUIDE_RU.md](docs/CONTENT_GUIDE_RU.md) for Russian). It
> explains what "good content" means for this specific model and pipeline.

### 📂 Files

View and edit files. Files are normally indexed automatically from a
Telegram channel posting workflow ([bot/handlers/files.py](bot/handlers/files.py)),
but the admin form lets you update `title` / `caption` / `category` /
`keywords` afterwards. Re-saving regenerates the embedding.

### 👥 Users

Registered Telegram users, their daily quota counter (`requests_left`), and
when the quota next resets.

### 🧠 Лаборатория (RAG Playground)

The single most useful page for tuning content. Type a query and see:

- Top-3 knowledge matches with cosine distances
- Top-5 file matches with per-file keyword gate status
- The final filter decision (🎯 "filter selects" / ⛔ "filter rejects")
- The actual AI answer

Use it in a tight loop with the knowledge/files edit forms when adding
content. If a query you expect to match isn't ranking, rewrite the content
or add keywords, save, retry.

### 📅 Расписание

View course schedules imported by the WSP scraper (rooms, instructors,
subjects).

---

## Telegram bot — what students see

- `/start` — greeting + main keyboard
- Free text questions — runs the RAG pipeline, returns answer + any
  attached files, appends 👍/👎 feedback buttons
- `🗺 Карта КБТУ` / `📅 Академический календарь` / `📚 РУПы` — category
  buttons that return all files in the matching category directly
- **Quota** — each user has `DAILY_LIMIT` AI requests per 24 hours. The
  quota is only consumed when an LLM call is actually made (retrieval hits
  and context is non-empty).

---

## Project layout

```
.
├── main.py                    # bot entrypoint, DB migration, router wiring
├── admin.py                   # Streamlit admin panel (all pages)
├── config.py                  # env loading
├── docker-compose.yml         # db + bot + admin services
├── Dockerfile                 # shared image
├── requirements.txt
│
├── bot/
│   ├── handlers/
│   │   ├── ai.py              # the main RAG handler + file filter
│   │   ├── commands.py        # /start and main keyboard
│   │   ├── files.py           # channel post → file indexing + category buttons
│   │   ├── feedback.py        # 👍/👎 inline callback handler
│   │   └── schedule.py        # schedule lookup keyboard flow
│   ├── keyboards/             # reply + inline keyboard builders
│   └── middlewares/
│       └── throttling.py      # per-user 3-second debounce
│
├── core/
│   ├── database.py            # async engine + Base
│   ├── models.py              # KnowledgeItem, FileItem, User, InteractionLog, knowledge_file_links
│   └── wsp_models.py          # Subject, Instructor, Room, Event, ...
│
├── services/
│   ├── ai_service.py          # Groq client + model-fallback chain + system prompt
│   ├── embeddings.py          # build_enriched_text + get_vector (E5)
│   └── repo.py                # all DB access (knowledge, files, users, quota, feedback)
│
├── wsp_scraper/               # Selenium-based WSP importer
├── scripts/                   # one-off utilities (seed data, imports)
├── tests/                     # pytest + asyncio integration tests
└── docs/
    ├── CONTENT_GUIDE_EN.md    # how to write knowledge + file entries (English)
    └── CONTENT_GUIDE_RU.md    # same, Russian
```

---

## Running tests

Tests require a running DB:

```bash
docker compose up -d db
python tests/test_file_attachments.py
```

The test file covers the file-filter gates (pure unit tests, no DB) plus
end-to-end curated-link and fallback flows against the real database.

---

## Troubleshooting

**Database connection error.** Check the `db` container is healthy:

```bash
docker compose ps
docker compose logs db
```

To run the full suite of tests, use:

```bash
python -m pytest -q tests
```

If `db` is unhealthy, the most common cause is a leftover `./postgres_data`
volume from a previous run with different credentials — remove it and
restart.

**AI error / "⚠️ Серверы сейчас перегружены".** The bot tries four models
in fallback order (see [services/ai_service.py](services/ai_service.py#L17-L22)).
If all four hit transient errors, the user sees this message. Check
`GROQ_API_KEY` in `.env` and your Groq quota.

**"По этому вопросу у меня нет данных" for a question you think should
work.** Retrieval found nothing within the `0.35` distance threshold. Open
the RAG Playground, paste the same query, and check distances. Usually the
fix is either (a) rewriting the knowledge entry's content to use the
vocabulary students actually type, or (b) adding more keywords. See the
content guide for details.

**Files don't attach even when clearly relevant.** See the
[content guide's troubleshooting section](docs/CONTENT_GUIDE_EN.md#8-troubleshooting)
— usually it's a missing keyword, a too-high distance, or an ambiguous gap
to a noise file.

**Code changes don't take effect.** Both `bot` and `admin` services mount
the repo as a volume, so `docker compose restart bot` is enough to pick up
Python changes. A full rebuild (`docker compose up --build`) is only needed
when `requirements.txt` or the `Dockerfile` changes.

---

## Further reading

- [docs/CONTENT_GUIDE_EN.md](docs/CONTENT_GUIDE_EN.md) — **read this before
  adding knowledge or files.** Explains field formats, length, language mixing,
  keyword strategy, and includes worked examples.
- [docs/CONTENT_GUIDE_RU.md](docs/CONTENT_GUIDE_RU.md) — Russian version.
- [bot/handlers/ai.py](bot/handlers/ai.py) — the RAG handler, file filter,
  and quota logic in ~190 readable lines.
- [services/ai_service.py](services/ai_service.py) — LLM system prompt and
  model fallback chain.
- [docs/load_testing.md](docs/load_testing.md) — Stress test report and load testing configuration overview.
