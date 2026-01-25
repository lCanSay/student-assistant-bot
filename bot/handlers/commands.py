from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.keyboards import get_main_keyboard

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    # Handle /start command.
    await message.answer(
        "Привет! Я твой студенческий помощник. Чем могу помочь?",
        reply_markup=get_main_keyboard()
    )
