from aiogram import Router
from aiogram.types import Message
from config import FAQ_FILE, FILES_FILE
from services.data_loader import load_data, search_knowledge_base, search_files
from services.ai_service import get_ai_answer

router = Router()

@router.message()
async def ai_chat_handler(message: Message):
    """
    Catch-all handler for AI chat.
    Uses RAG (simple keyword search) + Groq API + File Sending.
    STRICT MODE: If no context is found, do NOT query AI.
    """
    user_text = message.text or ""
    
    # Search Knowledge Base
    faq_data = load_data(FAQ_FILE)
    context = search_knowledge_base(user_text, faq_data)
    
    # Check for files
    files_data = load_data(FILES_FILE)
    found_files = search_files(user_text, files_data)
    
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
        ai_reply = await get_ai_answer(user_text, context)
        await wait_msg.delete()
        await message.answer(ai_reply)

    # Send files if found
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
            print(f"Error sending file {file_info.get('caption')}: {e}")
