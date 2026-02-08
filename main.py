import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN

from bot.handlers.commands import router as commands_router
from bot.handlers.info import router as info_router
from bot.handlers.files import router as files_router
from bot.handlers.ai import router as ai_router

logging.basicConfig(level=logging.INFO)

async def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in .env file.")
        return

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands_router)
    dp.include_router(info_router)
    dp.include_router(files_router)
    dp.include_router(ai_router)

    from bot.middlewares.throttling import ThrottlingMiddleware
    dp.message.middleware(ThrottlingMiddleware(ttl=5.0))


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
