# Deployment & Infrastructure

## Environment Variables

The application is configured via a `.env` file. All variables are loaded through `config.py` using `python-dotenv`.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | Yes | Telegram Bot API token (obtained from [@BotFather](https://t.me/BotFather)) |
| `GROQ_API_KEY` | Yes | API key for the Groq LLM service |
| `CHANNEL_ID` | Yes | Telegram channel ID for automatic file indexing (negative integer) |
| `POSTGRES_USER` | Yes | PostgreSQL username (used by the `db` container) |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `POSTGRES_DB` | Yes | PostgreSQL database name |
| `DB_HOST` | No | Database host. Defaults to `localhost` for local development; overridden to `db` inside Docker Compose |
| `DAILY_LIMIT` | No | Maximum AI requests per user per 24-hour window. Defaults to `5` |
| `WSP_LOGIN` | No | Login for the KBTU WSP portal (required only for the schedule scraper) |
| `WSP_PASSWORD` | No | Password for the WSP portal |

The `DATABASE_URL` is constructed automatically in `config.py`:

```
postgresql+asyncpg://postgres:postgres@{DB_HOST}:5432/kbtu_db
```

## Docker Configuration

### Services (`docker-compose.yml`)

The application consists of three Docker Compose services:

| Service | Image | Description |
|---|---|---|
| `db` | `ankane/pgvector:latest` | PostgreSQL with the pgvector extension pre-installed. Includes a health check (`pg_isready`) to ensure the bot does not start before the database is ready. Data is persisted via a bind mount to `./postgres_data`. |
| `bot` | `kbtu_rag_app:latest` (built from `Dockerfile`) | The Telegram bot process (`python main.py`). Depends on `db` with `condition: service_healthy`. Configured with `restart: unless-stopped`. |
| `admin` | `kbtu_rag_app:latest` (shared image with `bot`) | The Streamlit admin panel (`streamlit run admin.py`). Exposed on port `8501`. Mounts the project directory (`./:/app`) to enable live code reloading during development. Depends on `bot` with `condition: service_started`. |

### Dockerfile Design Decisions

#### IPv4-Forced APT Update

```dockerfile
RUN apt-get -o Acquire::ForceIPv4=true update && \
    apt-get -o Acquire::ForceIPv4=true install -y gcc libpq-dev
```

The `Acquire::ForceIPv4=true` flag forces `apt-get` to use IPv4 exclusively. This is a workaround for a known issue in Docker build environments (particularly on some CI runners and WSL setups) where IPv6 DNS resolution for Debian package mirrors can hang indefinitely, causing the build to time out. Forcing IPv4 ensures reliable package resolution in all network configurations.

#### Docker Layer Caching Strategy

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

COPY . .
```

The `Dockerfile` is structured to maximize Docker layer caching:

1. **`requirements.txt` is copied and installed first.** This layer is only invalidated when dependencies change, not when application code changes.
2. **The embedding model is downloaded in a separate `RUN` layer** before the application code is copied. The `intfloat/multilingual-e5-base` model (~1 GB) is downloaded from Hugging Face and cached within the Docker image. This ensures:
   - The model download layer is cached and reused across rebuilds that only change application code.
   - At runtime, the environment variables `TRANSFORMERS_OFFLINE=1` and `HF_HUB_OFFLINE=1` prevent any network calls to Hugging Face, eliminating external dependency at startup.
3. **Application code (`COPY . .`) is the final layer**, meaning code changes trigger only a lightweight copy operation, not a full re-download of dependencies or the model.

## CI/CD Pipeline

### GitHub Actions Workflow (`.github/workflows/docker-test.yml`)

The project includes a CI workflow named **"Docker Build Test"** that runs on:
- Every push to the `main` or `master` branch
- Every pull request targeting `main` or `master`

#### Pipeline Steps

| Step | Command | Purpose |
|---|---|---|
| Checkout | `actions/checkout@v4` | Clone the repository |
| Build | `docker compose build` | Verify that the Docker image builds successfully (dependencies install, model downloads, code copies without errors) |
| Create `.env` | `touch .env` | Create a minimal `.env` file to satisfy Docker Compose's `env_file` requirement |
| Start | `docker compose up -d` | Launch all services in detached mode |
| Health Check | `docker compose ps` | Verify that containers are running |
| Logs | `docker logs kbtu_rag_bot` / `docker logs kbtu_rag_admin` | Inspect container startup output for errors |
| Cleanup | `docker compose down` | Stop and remove all containers |

The primary purpose of this pipeline is to act as a **build verification gate**: it ensures that every commit to the main branch produces a valid, buildable Docker image. Since the bot requires live Telegram and Groq API tokens to function, the pipeline does not perform runtime integration tests — it validates the infrastructure layer only.
