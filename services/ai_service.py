from groq import AsyncGroq
from config import GROQ_API_KEY

# Initialize the Groq client
client = None

def get_client():
    global client
    if client is None:
        if GROQ_API_KEY:
            client = AsyncGroq(api_key=GROQ_API_KEY)
    return client

async def get_ai_answer(user_question: str, context: str) -> str:
    """
    Get an answer from the AI model based on the question and context.
    """
    client = get_client()
    if not client:
        return "⚠️ Ошибка: API ключ не найден. Пожалуйста, настройте GROQ_API_KEY."

    system_prompt = (
        "Ты помощник студента. Отвечай ТОЛЬКО на основе предоставленного ниже контекста." 
        "Если в контексте НЕТ прямого ответа на вопрос, ЗАПРЕЩЕНО выдумывать или комбинировать не связанные факты." 
        "В таком случае ответь: 'К сожалению, в моей базе знаний нет информации по этому вопросу'."
    )
    
    user_content = f"Вопрос: {user_question}\n\nКонтекст:\n{context}" if context else user_question

    try:
        chat_completion = await client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_content,
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Произошла ошибка при обращении к AI: {str(e)}"
