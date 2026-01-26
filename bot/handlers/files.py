from aiogram import Router, F, types
from aiogram.types import Message
from core.database import async_session
from services.repo import Repo

router = Router()

@router.channel_post(F.document | F.photo)
async def handle_new_file_post(message: Message):
    """
    Handle new file posts in the channel.
    Autosaves files to Database.
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
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    else:
        return

    async with async_session() as session:
        repo = Repo(session)
        # Note: Repo.add_file automatically generates embeddings for the caption
        await repo.add_file(file_id, caption, keywords, file_type)
    
    try:
        await message.react([types.ReactionTypeEmoji(emoji="👍")])
    except:
        pass

@router.edited_channel_post(F.document | F.photo)
async def handle_edited_file_post(message: Message):
    # TODO: Implement update logic in Repo if needed
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
