import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers import router

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    # Load environment variables
    load_dotenv()
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("Error: BOT_TOKEN not found in .env file.")
        return

    # Initialize Bot and Dispatcher
    bot = Bot(token=bot_token)
    dp = Dispatcher()

    # Include routers
    dp.include_router(router)

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
