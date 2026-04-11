import logging
import re

from aiogram import Router
from aiogram.types import Message

import services.repo as repo
from bot.keyboards.feedback import get_feedback_keyboard
from config import DAILY_LIMIT
from core.database import async_session
from services.ai_service import AIConfigError, AllModelsUnavailableError, get_ai_answer

logger = logging.getLogger(__name__)


async def _safe_delete(msg: Message) -> None:
    try:
        await msg.delete()
    except Exception:
        pass

router = Router()

_VALID_QUERY_RE = re.compile(r'[a-zA-Zа-яА-ЯёЁәғқңөұүһіӘҒҚҢӨҰҮҺІ]')

_MAX_FALLBACK_DISTANCE = 0.20
_MIN_GAP = 0.05


def _filter_fallback_files(candidates: list, user_text: str) -> list:
    """Return at most one file that passes all three gates:
    1. At least one file keyword is a substring of the user query
    2. Distance ≤ _MAX_FALLBACK_DISTANCE
    3. Clear-winner gap vs second keyword-matching candidate ≥ _MIN_GAP

    Keyword gate runs first so that no-keyword noise files cannot block a
    real match via the gap check.
    """
    if not candidates:
        return []
    query_lower = user_text.lower()
    # Keep only candidates whose keywords overlap the query
    kw_matched = [
        (f, d) for f, d in candidates
        if (f.keywords or []) and any(k.lower() in query_lower for k in f.keywords)
    ]
    if not kw_matched:
        return []
    top, top_dist = kw_matched[0]
    if top_dist > _MAX_FALLBACK_DISTANCE:
        return []
    if len(kw_matched) > 1:
        _, second_dist = kw_matched[1]
        if second_dist - top_dist < _MIN_GAP:
            return []  # ambiguous among keyword-matching files
    return [top]


def _is_valid_query(text: str) -> bool:
    """Return True if the text looks like a real user question."""
    stripped = text.strip()
    if len(stripped) < 3:
        return False
    if stripped.isdigit():
        return False
    if not _VALID_QUERY_RE.search(stripped):
        return False
    return True


@router.message()
async def ai_chat_handler(message: Message):
    """
    Catch-all handler for AI chat.
    Uses RAG (Vector Search) + Groq API + File Sending.
    """
    user_text = message.text or ""

    # --- Input pre-filter (no DB, no quota) ---
    if not _is_valid_query(user_text):
        await message.answer(
            "Пожалуйста, введите осмысленный вопрос (минимум 3 символа)."
        )
        return

    async with async_session() as session:
        # Ensure user exists (in case they didn't press /start)
        user = await repo.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )

        # --- Vector search (no quota consumed yet) ---
        knowledge_with_score = await repo.search_knowledge(session, user_text, limit=3)
        knowledge_items = [(item, dist) for item, dist in knowledge_with_score if dist <= 0.35]

        # Build context: include title as a header when available
        context_parts = []
        for item, dist in knowledge_items:
            if item.title:
                context_parts.append(f"[{item.title}]\n{item.content}")
            else:
                context_parts.append(item.content)
        context = "\n\n---\n\n".join(context_parts)

        # --- Curated attachments (primary path) ---
        # Files linked explicitly to matched knowledge entries are always sent.
        curated_files: list = []
        seen_file_ids: set[int] = set()
        for item, _ in knowledge_items:
            for f in await repo.get_linked_files(session, item.id):
                if f.id not in seen_file_ids:
                    curated_files.append(f)
                    seen_file_ids.add(f.id)

        # --- File vector search (always runs; strict 3-gate filter) ---
        # Returns at most one file. Runs even when knowledge matched so that
        # a clearly-relevant file isn't silently dropped because an unrelated
        # knowledge entry absorbed the query.
        file_candidates = await repo.search_files(session, user_text, limit=5)
        fallback_files = [
            f for f in _filter_fallback_files(file_candidates, user_text)
            if f.id not in seen_file_ids
        ]

        valid_files = curated_files + fallback_files

        # --- No context found: respond without consuming quota or LLM ---
        if not context:
            if valid_files:
                await message.answer(
                    "ℹ️ Я нашел файлы по вашему запросу, но текстовой справки у меня пока нет."
                )
            else:
                await message.answer(
                    "К сожалению, у меня пока нет информации по этому вопросу. "
                    "Попробуйте переформулировать или обратитесь в деканат."
                )
            for file_item in valid_files:
                try:
                    if file_item.type == "document":
                        await message.answer_document(document=file_item.file_id)
                    elif file_item.type == "photo":
                        await message.answer_photo(photo=file_item.file_id)
                except Exception as e:
                    print(f"Error sending file {file_item.caption}: {e}")
            return

        # --- Context found: NOW consume quota ---
        allowed = await repo.check_and_increment_quota(session, user)
        if not allowed:
            await session.refresh(user)
            await message.answer(
                f"Лимит исчерпан ({DAILY_LIMIT} запросов/24ч). "
                f"Доступ восстановится в {user.quota_reset_at}."
            )
            return

    # --- Call LLM ---
    wait_msg = await message.answer("⏳ Думаю...")
    try:
        ai_reply = await get_ai_answer(user_text, context)
    except AllModelsUnavailableError as e:
        await _safe_delete(wait_msg)
        await message.answer("⚠️ Серверы сейчас перегружены. Пожалуйста, попробуйте позже.")
        logger.warning("All models unavailable for user %s: %s", message.from_user.id, e)
        return
    except AIConfigError as e:
        await _safe_delete(wait_msg)
        await message.answer("⚠️ Сервис временно недоступен.")
        logger.error("AI misconfigured: %s", e)
        return
    except Exception:
        await _safe_delete(wait_msg)
        await message.answer("⚠️ Ошибка обращения к AI серверу.")
        logger.exception("Unexpected AI error for user %s", message.from_user.id)
        return

    await _safe_delete(wait_msg)

    async with async_session() as session:
        interaction_id = await repo.log_interaction(
            session, message.from_user.id, user_text, ai_reply
        )
    await message.answer(
        ai_reply,
        reply_markup=get_feedback_keyboard(interaction_id),
    )

    for file_item in valid_files:
        try:
            if file_item.type == "document":
                await message.answer_document(document=file_item.file_id)
            elif file_item.type == "photo":
                await message.answer_photo(photo=file_item.file_id)
        except Exception as e:
            print(f"Error sending file {file_item.caption}: {e}")
