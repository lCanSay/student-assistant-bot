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
        # Search Knowledge Base (Vector Search)
        knowledge_items = await repo.search_knowledge(session, user_text, limit=3)
        context = "\n".join([item.content for item in knowledge_items])
        
        # Check for files (Vector Search)
        found_files = await repo.search_files(session, user_text, limit=3)
    
    # Decision Logic
    if not context:
        if found_files:
            # Files found, but no text context
            await message.answer("ℹ️ Я нашел файлы по вашему запросу, но текстовой справки у меня пока нет.")
        else:
            # Nothing found
            await message.answer("❌ К сожалению, я пока не знаю ответа на этот вопрос. Попробуйте переформулировать или обратитесь в деканат.")
            return
    else:
        # Context found, query AI
        wait_msg = await message.answer("⏳ Думаю...")
        try:
            ai_reply = await get_ai_answer(user_text, context)
            await wait_msg.delete()
            await message.answer(ai_reply)
        except Exception as e:
            await wait_msg.edit_text("⚠️ Ошибка обращения к AI серверу.")
            print(f"AI Error: {e}")

    # Send files if found
    # TODO: Fix file sending logic
    
    # for file_item in found_files:
    #     try:
    #         if file_item.type == "document":
    #             await message.answer_document(document=file_item.file_id, caption=file_item.caption)
    #         elif file_item.type == "photo":
    #             await message.answer_photo(photo=file_item.file_id, caption=file_item.caption)
    #     except Exception as e:
    #         print(f"Error sending file {file_item.caption}: {e}")
