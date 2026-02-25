from aiogram import Router, F, types
from aiogram.types import Message
from aiogram.utils.media_group import MediaGroupBuilder
from core.database import async_session
import services.repo as repo

router = Router()

# ── Hashtag → category mapping ──────────────────────────────────────────────
HASHTAG_CATEGORY_MAP: dict[str, str] = {
    "#карта": "map",
    "#календарь": "calendar",
    "#руп": "rup",
}


def _extract_category(caption: str) -> str | None:
    """Return the first matching category from caption hashtags, or None."""
    lower = caption.lower()
    for tag, category in HASHTAG_CATEGORY_MAP.items():
        if tag in lower:
            return category
    return None


# ── Channel post handler (auto-save files from channel) ─────────────────────
@router.channel_post(F.document | F.photo)
@router.edited_channel_post(F.document | F.photo)
async def handle_file_post(message: Message):
    """
    Handle new and edited file posts in the channel.
    Autosaves/Updates files to Database.
    Parses hashtags to assign category.
    """
    from config import CHANNEL_ID

    if str(message.chat.id) != str(CHANNEL_ID):
        return

    raw_caption = message.caption or ""
    caption = raw_caption.strip()
    category = _extract_category(caption)

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
        await repo.upsert_file(
            session=session,
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_name=file_name,
            caption=caption,
            file_type=file_type,
            category=category,
        )

    try:
        await message.react([types.ReactionTypeEmoji(emoji="👍")])
    except Exception:
        pass


# ── MediaGroup reply-keyboard handlers ──────────────────────────────────────
async def _send_files_by_category(message: Message, category: str) -> None:
    """Fetch files by category and send them as a MediaGroup."""
    async with async_session() as session:
        files = await repo.get_files_by_category(session, category)

    if not files:
        await message.answer("Файлы пока не загружены.")
        return

    builder = MediaGroupBuilder()
    for file in files:
        builder.add(type=file.type, media=file.file_id)

    await message.answer_media_group(media=builder.build())


@router.message(F.text == "🗺 Карта КБТУ")
async def send_uni_map(message: Message):
    await _send_files_by_category(message, category="map")


@router.message(F.text == "📅 Академ. календарь")
async def send_academic_calendar(message: Message):
    await _send_files_by_category(message, category="calendar")


@router.message(F.text == "📚 РУПы")
async def send_rup(message: Message):
    await _send_files_by_category(message, category="rup")


# ── Debug handler (send a file to get its file_id) ──────────────────────────
@router.message(F.content_type.in_({"document", "photo"}))
async def get_file_id_debug(message: Message):
    # Получаем file_id отправляя боту файл
    if message.document:
        file_id = message.document.file_id
        file_type = "document"
        name = message.document.file_name
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
        name = "photo.jpg"

    response = (
        f"📂 **Тип:** `{file_type}`\n"
        f"🏷 **Имя:** `{name}`\n"
        f"🆔 **ID:**\n`{file_id}`"
    )
    await message.answer(response, parse_mode="Markdown")
