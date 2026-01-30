from aiogram import Router, F, types
from aiogram.types import Message
from core.database import async_session
import services.repo as repo

router = Router()

@router.channel_post(F.document | F.photo)
@router.edited_channel_post(F.document | F.photo)
async def handle_file_post(message: Message):
    """
    Handle new and edited file posts in the channel.
    Autosaves/Updates files to Database.
    Format: "Caption"
    """
    from config import CHANNEL_ID
    
    if str(message.chat.id) != str(CHANNEL_ID):
        return

    raw_caption = message.caption or ""
    caption = raw_caption.strip()
    
    if message.document:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        file_name = message.document.file_name or "document"
        file_type = "document"
    elif message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        file_unique_id = photo.file_unique_id
        file_name = "photo.jpg"
        file_type = "photo"
    else:
        return

    async with async_session() as session:
        # Upsert file (handles both new and edited posts)
        await repo.upsert_file(
            session=session, 
            file_id=file_id, 
            file_unique_id=file_unique_id, 
            file_name=file_name, 
            caption=caption, 
            file_type=file_type
        )
    
    try:
        await message.react([types.ReactionTypeEmoji(emoji="👍")])
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
