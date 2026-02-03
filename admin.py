import streamlit as st
import asyncio
import pandas as pd
from core.database import async_session
import services.repo as repo
from services.ai_service import get_ai_answer
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="RAG Bot Admin", layout="wide")

def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

# Sidebar
st.sidebar.title("Admin Panel")
page = st.sidebar.radio("Navigation", ["📝 База Знаний", "🧠 Лаборатория", "📊 Аналитика"])

# PAGE 1: KNOWLEDGE BASE
if page == "📝 База Знаний":
    st.title("Управление Базой Знаний")
    
    # 1. Add New
    with st.expander("➕ Добавить новую запись"):
        with st.form("add_new_form"):
            new_cat = st.text_input("Категория (Topic)", value="General")
            new_keywords = st.text_input("Ключевые слова(keywords)", value=[])
            new_content = st.text_area("Содержание (Content)")
            
            submitted = st.form_submit_button("Сохранить")
            if submitted and new_content:
                async def add_logic():
                    async with async_session() as session:
                        await repo.add_knowledge(session, new_content, new_cat, new_keywords)
                run_async(add_logic())
                st.success("Запись добавлена!")
                st.rerun()

    # 2. View & Edit
    st.subheader("Список записей")
    
    async def get_data():
        async with async_session() as session:
            return await repo.get_all_knowledge(session, limit=100)
    
    items = run_async(get_data())
    
    if items:
        df = pd.DataFrame([
            {"id": i.id, "category": i.category, "content": i.content} 
            for i in items
        ])
        
        st.dataframe(
            df,
            column_config={
                "id": st.column_config.NumberColumn(format="%d"),
                "category": st.column_config.TextColumn("Категория"),
                "content": st.column_config.TextColumn("Содержание", width="large")
            },
            hide_index=True,
            use_container_width=True
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            edit_id = st.number_input("ID для редактирования/удаления", min_value=1, step=1)
        
        selected_item = next((x for x in items if x.id == edit_id), None)
        
        if selected_item:
            with st.form("edit_form"):
                st.write(f"Редактирование ID: {edit_id}")
                edit_cat = st.text_input("Категория", value=selected_item.category)
                edit_content = st.text_area("Содержание", value=selected_item.content)
                
                c_save, c_del = st.columns(2)
                with c_save:
                    save_click = st.form_submit_button("💾 Сохранить изменения")
                with c_del:
                    del_click = st.form_submit_button("🗑 Удалить запись", type="primary")
                
                if save_click:
                    async def save_logic():
                        async with async_session() as session:
                            await repo.update_knowledge(session, edit_id, edit_content, edit_cat)
                    if run_async(save_logic()):
                        st.success("Обновлено!")
                        st.rerun()
                    else:
                        st.error("Ошибка при обновлении.")

                if del_click:
                    async def del_logic():
                        async with async_session() as session:
                            await repo.delete_knowledge(session, edit_id)
                    if run_async(del_logic()):
                        st.warning("Удалено!")
                        st.rerun()
                    else:
                        st.error("Ошибка при удалении.")

# PAGE 2: PLAYGROUND
elif page == "🧠 Лаборатория":
    st.title("RAG Playground (Тест Поиска)")
    
    query = st.text_input("Введите вопрос для бота:")
    
    if st.button("Искать и Генерировать"):
        if query:
            st.write("🔎 Поиск в базе знаний...")
            
            async def test_logic():
                async with async_session() as session:

                    knowledge_with_score = await repo.search_knowledge(session, query, limit=3)
                    
                    context_items = []
                    st.subheader("Найденный контекст:")
                    for item, dist in knowledge_with_score:
                        cols = st.columns([1, 4])
                        cols[0].metric("Distance", f"{dist:.4f}")
                        cols[1].info(f"**[{item.category}]** {item.content}")
                        context_items.append(item.content)
                    
                    context = "\n".join(context_items)
                    
                    st.write("🤖 Генерация ответа AI...")
                    response = await get_ai_answer(query, context)
                    return response
            
            ai_resp = run_async(test_logic())
            
            st.subheader("Ответ AI:")
            st.success(ai_resp)

# PAGE 3: ANALYTICS
elif page == "📊 Аналитика":
    st.title("Аналитика")
    st.write("Здесь будет статистика использования бота.")
    
    # Dummy chart
    data = pd.DataFrame({
        'day': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        'queries': [10, 25, 15, 30, 45]
    })
    st.bar_chart(data.set_index('day'))

    st.caption("Coming soon...")
