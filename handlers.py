import json
import os
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message
from keyboards import get_main_keyboard
from utils import load_data, search_knowledge_base, search_files, save_file_entry, update_file_entry
from ai_service import get_ai_answer

router = Router()

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SCHEDULE_FILE = os.path.join(DATA_DIR, 'schedule.json')
ROOMS_FILE = os.path.join(DATA_DIR, 'rooms.json')
CONTACTS_FILE = os.path.join(DATA_DIR, 'contacts.json')
FAQ_FILE = os.path.join(DATA_DIR, 'faq.json')
FILES_FILE = os.path.join(DATA_DIR, 'files.json')

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


@router.channel_post(F.document | F.photo)
async def handle_new_file_post(message: Message):
    """
    Handle new file posts in the channel.
    Autosaves files to files.json.
    Format: "Caption: tag1, tag2"
    """
    raw_caption = message.caption or ""
    
    if ":" in raw_caption:
        parts = raw_caption.split(":", 1)
        caption = parts[0].strip()
        keywords = [k.strip().lower() for k in parts[1].split(",") if k.strip()]
    else:
        # Fallback to old behavior
        caption = raw_caption.strip()
        keywords = [k.strip().lower() for k in raw_caption.split(",") if k.strip()]
    
    if message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    else:
        return

    entry = {
        "file_id": file_id,
        "keywords": keywords,
        "caption": caption,
        "type": file_type
    }
    
    save_file_entry(entry, FILES_FILE)
    
    try:
        await message.react([types.ReactionTypeEmoji(emoji="👍")])
    except:
        pass

@router.edited_channel_post(F.document | F.photo)
async def handle_edited_file_post(message: Message):
    """
    Handle edited file posts in the channel.
    Updates existing file entry in files.json.
    Format: "Caption: tag1, tag2"
    """
    raw_caption = message.caption or ""
    
    if ":" in raw_caption:
        parts = raw_caption.split(":", 1)
        caption = parts[0].strip()
        keywords = [k.strip().lower() for k in parts[1].split(",") if k.strip()]
    else:
        caption = raw_caption.strip()
        keywords = [k.strip().lower() for k in raw_caption.split(",") if k.strip()]
    
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    else:
        return

    updated = update_file_entry(file_id, keywords, caption, FILES_FILE)
    
    if updated:
        try:
            await message.react([types.ReactionTypeEmoji(emoji="⚡")])
        except:
            pass

@router.message(F.content_type.in_({'document', 'photo'}))
async def get_file_id_debug(message: Message):
    # Получаем file_id отправляя боту файл
    if message.document:
        file_id = message.document.file_id
        file_type = "document"
        name = message.document.file_name
    elif message.photo:
        # У фото несколько размеров, берем самый большой (последний)
        file_id = message.photo[-1].file_id
        file_type = "photo"
        name = "photo.jpg"
    
    response = (
        f"📂 **Тип:** `{file_type}`\n"
        f"🏷 **Имя:** `{name}`\n"
        f"🆔 **ID:**\n`{file_id}`" 
    )
    await message.answer(response, parse_mode="Markdown")

@router.message()
async def ai_chat_handler(message: Message):
    """
    Catch-all handler for AI chat.
    Uses RAG (simple keyword search) + Groq API + File Sending.
    """
    user_text = message.text or ""
    
    # 1. Search Knowledge Base
    faq_data = load_data(FAQ_FILE)
    context = search_knowledge_base(user_text, faq_data)
    
    # 2. Get AI Answer
    wait_msg = await message.answer("⏳ Думаю...")
    ai_reply = await get_ai_answer(user_text, context)
    await wait_msg.delete()
    await message.answer(ai_reply)

    # 3. Check for files to send
    files_data = load_data(FILES_FILE)
    found_files = search_files(user_text, files_data)
    
    for file_info in found_files:
        try:
            file_id = file_info.get("file_id")
            caption = file_info.get("caption")
            file_type = file_info.get("type")
            
            if file_type == "document":
                await message.answer_document(document=file_id, caption=caption)
            elif file_type == "photo":
                await message.answer_photo(photo=file_id, caption=caption)
        except Exception as e:
            # Silently fail or log error if file_id is invalid to not disrupt the chat
            print(f"Error sending file {file_info.get('caption')}: {e}")
