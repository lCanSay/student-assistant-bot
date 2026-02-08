from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.keyboards import get_main_keyboard

from core.database import async_session
import services.repo as repo

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    # Register user
    async with async_session() as session:
        await repo.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username
        )
    
    # Handle /start command.
    await message.answer(
        "Привет! Я твой студенческий помощник. Чем могу помочь?",
        reply_markup=get_main_keyboard()
    )
