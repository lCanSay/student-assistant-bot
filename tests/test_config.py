import importlib
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def test_database_url_default_uses_db_host(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "dbhost")

    config = importlib.reload(importlib.import_module("config"))

    assert config.DATABASE_URL == "postgresql+asyncpg://postgres:postgres@dbhost:5432/kbtu_db"
