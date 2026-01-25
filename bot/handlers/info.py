import json
from aiogram import Router, F
from aiogram.types import Message
from config import SCHEDULE_FILE, ROOMS_FILE, CONTACTS_FILE
from services.data_loader import load_data

router = Router()

@router.message(F.text == "📅 Мое расписание")
async def show_schedule(message: Message):
    """
    Handle schedule request.
    Reads from schedule.json and shows Monday's schedule.
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
    Reads from rooms.json and filters by is_free=True.
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
