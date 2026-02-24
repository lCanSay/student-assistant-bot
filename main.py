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
# Ensure all models are imported so Base.metadata knows about them
import core.models  # noqa: F401
import core.wsp_models  # noqa: F401

logging.basicConfig(level=logging.INFO)

async def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in .env file.")
        return

    # Ensure database tables exist
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables ready.")

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands_router)
    dp.include_router(files_router)
    dp.include_router(schedule_router)
    dp.include_router(feedback_router)
    dp.include_router(ai_router)

    dp.message.middleware(ThrottlingMiddleware(ttl=3.0))


    print("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")
