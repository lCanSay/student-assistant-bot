import json
import os
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message
from keyboards import get_main_keyboard
from utils import load_data, search_knowledge_base
from ai_service import get_ai_answer

router = Router()

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SCHEDULE_FILE = os.path.join(DATA_DIR, 'schedule.json')
ROOMS_FILE = os.path.join(DATA_DIR, 'rooms.json')
CONTACTS_FILE = os.path.join(DATA_DIR, 'contacts.json')
FAQ_FILE = os.path.join(DATA_DIR, 'faq.json')

@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Handle /start command.
    """
    await message.answer(
        "Привет! Я твой студенческий помощник. Чем могу помочь?",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "📅 Мое расписание")
async def show_schedule(message: Message):
    """
    Handle schedule request.
    Reads from data/schedule.json and shows Monday's schedule.
    """
    try:
        with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        group = data.get("group", "Unknown")
        monday_schedule = data.get("Monday", [])
        
        if not monday_schedule:
            await message.answer(f"Расписание для группы {group} на Понедельник не найдено.")
            return

        text_lines = [f"📅 Расписание на Понедельник ({group}):\n"]
        for lesson in monday_schedule:
            text_lines.append(
                f"⏰ {lesson['time']} — {lesson['subject']}\n"
                f"   📍 {lesson['room']} ({lesson['type']})"
            )
        
        await message.answer("\n".join(text_lines))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        await message.answer(f"Ошибка при чтении расписания: {e}")

@router.message(F.text == "🔍 Свободные аудитории")
async def show_free_rooms(message: Message):
    """
    Handle free rooms request.
    Reads from data/rooms.json and filters by is_free=True.
    """
    try:
        with open(ROOMS_FILE, 'r', encoding='utf-8') as f:
            rooms = json.load(f)
        
        free_rooms = [r['id'] for r in rooms if r.get('is_free')]
        
        if free_rooms:
            await message.answer(f"✅ Свободные аудитории: {', '.join(free_rooms)}")
        else:
            await message.answer("❌ К сожалению, сейчас нет свободных аудиторий.")
            
    except (FileNotFoundError, json.JSONDecodeError) as e:
        await message.answer(f"Ошибка при поиске аудиторий: {e}")

@router.message(F.text == "📞 Контакты")
async def show_contacts(message: Message):
    """
    Handle contacts request using contacts.json.
    """
    contacts = load_data(CONTACTS_FILE)
    if not contacts:
        await message.answer("ℹ️ Контакты временно недоступны.")
        return

    text_lines = ["📞 **Контакты:**\n"]
    for key, value in contacts.items():
        text_lines.append(value)
    
    await message.answer("\n\n".join(text_lines))

@router.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    """
    Handle help request.
    """
    await message.answer(
        "Я могу показать расписание, найти свободную аудиторию или подсказать контакты.\n"
        "Вы также можете задать мне вопрос, и я постараюсь ответить!"
    )

@router.message()
async def ai_chat_handler(message: Message):
    """
    Catch-all handler for AI chat.
    Uses RAG (simple keyword search) + Groq API.
    """
    user_text = message.text or ""
    
    # 1. Search Knowledge Base
    faq_data = load_data(FAQ_FILE)
    context = search_knowledge_base(user_text, faq_data)
    
    # 2. Get AI Answer
    # Show typing status could be good, but keeping it simple as per request
    wait_msg = await message.answer("⏳ Думаю...")
    
    ai_reply = await get_ai_answer(user_text, context)
    
    await wait_msg.delete()
    await message.answer(ai_reply)
