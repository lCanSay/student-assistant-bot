import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Data directory
DATA_DIR = BASE_DIR / 'data'
SCHEDULE_FILE = DATA_DIR / 'schedule.json'
ROOMS_FILE = DATA_DIR / 'rooms.json'
CONTACTS_FILE = DATA_DIR / 'contacts.json'
FAQ_FILE = DATA_DIR / 'faq.json'
FILES_FILE = DATA_DIR / 'files.json'

# Secrets
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DB_HOST = os.getenv("DB_HOST", "localhost")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql+asyncpg://postgres:postgres@{DB_HOST}:5432/kbtu_db")
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
