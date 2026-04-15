import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN

from bot.handlers.commands import router as commands_router
from bot.handlers.files import router as files_router
from bot.handlers.schedule import router as schedule_router
from bot.handlers.feedback import router as feedback_router
from bot.handlers.ai import router as ai_router
from bot.middlewares.throttling import ThrottlingMiddleware

from sqlalchemy import text
from core.database import engine, Base

import core.models
import core.wsp_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in .env file")
        return

    # Ensure database tables exist and migrate schema
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Idempotent migrations: add new columns where missing
        for stmt in [
            "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS title VARCHAR(255)",
            "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS keywords TEXT[]",
            "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS title VARCHAR(255)",
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS keywords TEXT[]",
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
        ]:
            await conn.execute(text(stmt))
    logger.info("Database tables ready")

    # Preload embedding model (avoids 30-34 s cold start on first query)
    from services.embeddings import preload_model
    preload_model()

    # Start Prometheus metrics server
    from services.metrics import start_metrics_server, BOT_INFO
    BOT_INFO.info({"version": "1.0.0"})
    start_metrics_server(port=9100)

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands_router)
    dp.include_router(files_router)
    dp.include_router(schedule_router)
    dp.include_router(feedback_router)
    dp.include_router(ai_router)

    dp.message.middleware(ThrottlingMiddleware(ttl=3.0))

    logger.info("Starting bot polling")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
