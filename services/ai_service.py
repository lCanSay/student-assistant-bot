from groq import AsyncGroq
from config import GROQ_API_KEY

client = None

def get_client():
    global client
    if client is None:
        if GROQ_API_KEY:
            client = AsyncGroq(api_key=GROQ_API_KEY)
    return client

async def get_ai_answer(user_question: str, context: str) -> str:
    client = get_client()
    if not client:
        return "⚠️ Ошибка: API ключ не найден. Пожалуйста, настройте GROQ_API_KEY."

    system_prompt = (
        "Ты — умный помощник студента КБТУ (Казахстанско-Британский Технический Университет). "
        "Тебе предоставлены фрагменты из базы знаний, релевантные вопросу студента.\n\n"
        "ПРАВИЛА:\n"
        "1. Отвечай ТОЛЬКО на основе предоставленного контекста. НЕ выдумывай и НЕ додумывай информацию.\n"
        "2. Если контекст содержит ответ — сформулируй чёткий, структурированный ответ СВОИМИ СЛОВАМИ. "
        "НЕ копируй текст дословно, а извлеки и перефразируй ключевую информацию.\n"
        "3. Если вопрос требует перечисления шагов или условий — используй нумерованный список.\n"
        "4. Давай полный ответ: объясни ЧТО, КАК, КОГДА и ГДЕ, если эта информация есть в контексте.\n"
        "5. Если в контексте НЕТ ответа на вопрос — ответь РОВНО одним словом: NO_INFO\n"
        "6. Отвечай на том же языке, на котором задан вопрос.\n"
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
            temperature=0.3,
            max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Произошла ошибка при обращении к AI: {str(e)}"
