from aiogram import Router, F, types
from aiogram.types import Message
from config import FILES_FILE
from services.data_loader import save_file_entry, update_file_entry

router = Router()

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
        pass # Ignore reaction errors (e.g. if bot is not allowed to react)

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
