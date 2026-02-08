from aiogram import Router
from aiogram.types import Message
from core.database import async_session
import services.repo as repo
from services.ai_service import get_ai_answer

router = Router()

@router.message()
async def ai_chat_handler(message: Message):
    """
    Catch-all handler for AI chat.
    Uses RAG (Vector Search) + Groq API + File Sending.
    """
    user_text = message.text or ""
    
    async with async_session() as session:
        # Ensure user exists (in case they didn't press /start)
        user = await repo.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username
        )

        # Check Quota
        allowed = await repo.check_and_increment_quota(session, user)
        if not allowed:
            await session.refresh(user)
            await message.answer(f"Limit reached (50 requests/24h). Access restores at {user.quota_reset_at}.")
            return

        # Search Knowledge Base (Vector Search)
        knowledge_with_score = await repo.search_knowledge(session, user_text, limit=3)
        knowledge_items = [item for item, dist in knowledge_with_score if dist <= 0.7]
                
        context = "\n".join([item.content for item in knowledge_items])

        found_files_with_score = await repo.search_files(session, user_text, limit=3)
        
        # Filter by threshold (distance <= 0.5 means good match)
        valid_files = []
        for file_item, distance in found_files_with_score:
            if distance <= 0.2:
                valid_files.append(file_item)
    
    wait_msg = await message.answer("⏳ Думаю...")
    try:
        if not context:
            ai_reply = "NO_INFO"
        else:
            ai_reply = await get_ai_answer(user_text, context)
        
        await wait_msg.delete()
        
        if "NO_INFO" in ai_reply:
            if valid_files:
                await message.answer("ℹ️ Я нашел файлы по вашему запросу, но текстовой справки у меня пока нет.")
            else:
                await message.answer("❌ К сожалению, я пока не знаю ответа на этот вопрос. Попробуйте переформулировать или обратитесь в деканат.")
        else:
            await message.answer(ai_reply)

    except Exception as e:
        await wait_msg.edit_text("⚠️ Ошибка обращения к AI серверу.")
        print(f"AI Error: {e}")
    
    for file_item in valid_files:
        try:
            if file_item.type == "document":
                await message.answer_document(document=file_item.file_id)
            elif file_item.type == "photo":
                await message.answer_photo(photo=file_item.file_id)
        except Exception as e:
            print(f"Error sending file {file_item.caption}: {e}")
