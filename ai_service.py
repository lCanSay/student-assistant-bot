import os
from groq import AsyncGroq

# Initialize the Groq client
# Ensure GROQ_API_KEY is set in environment variables
client = None

def get_client():
    global client
    if client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            client = AsyncGroq(api_key=api_key)
    return client

async def get_ai_answer(user_question: str, context: str) -> str:
    """
    Get an answer from the AI model based on the question and context.
    """
    client = get_client()
    if not client:
        return "⚠️ Ошибка: API ключ не найден. Пожалуйста, настройте GROQ_API_KEY."

    system_prompt = (
        "Ты помощник студента КБТУ. Отвечай кратко, используя ТОЛЬКО предоставленный контекст. "
        "Если контекста нет, отвечай вежливо, что не знаешь."
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
