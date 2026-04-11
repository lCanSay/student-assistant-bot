import streamlit as st
import asyncio
import pandas as pd
from core.database import async_session
import services.repo as repo
from services.ai_service import get_ai_answer
from dotenv import load_dotenv

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.wsp_models import Subject, ScheduleEvent, Instructor, Room
from core.models import InteractionLog

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
page = st.sidebar.radio("Navigation", ["📝 База Знаний", "📂 Файлы", "👥 Пользователи", "💬 Обратная связь", "🧠 Лаборатория", "📅 Расписание"])

# PAGE 1: KNOWLEDGE BASE
if page == "📝 База Знаний":
    st.title("Управление Базой Знаний")

    # 1. Add New
    with st.expander("➕ Добавить новую запись"):
        with st.form("add_new_form"):
            new_title = st.text_input("Название (Title)", placeholder="напр. Retake / Пересдача")
            new_cat = st.text_input("Категория (Category)", value="General", placeholder="напр. Учебный процесс")
            new_keywords = st.text_input("Ключевые слова (Keywords)", placeholder="через запятую: retake, пересдача, fx")
            new_content = st.text_area("Содержание (Content)")

            submitted = st.form_submit_button("Сохранить")
            if submitted and new_content:
                kw_list = [kw.strip() for kw in new_keywords.split(",") if kw.strip()] if new_keywords else None
                async def add_logic():
                    async with async_session() as session:
                        await repo.add_knowledge(session, new_content, new_cat, new_title or None, kw_list)
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
            {
                "id": i.id,
                "title": i.title or "",
                "category": i.category or "",
                "keywords": ", ".join(i.keywords) if i.keywords else "",
                "content": i.content[:120] + "…" if len(i.content) > 120 else i.content,
                "updated_at": i.updated_at.strftime("%d.%m.%Y %H:%M") if i.updated_at else "—",
            }
            for i in items
        ])

        st.dataframe(
            df,
            column_config={
                "id": st.column_config.NumberColumn(format="%d", width="small"),
                "title": st.column_config.TextColumn("Название"),
                "category": st.column_config.TextColumn("Категория"),
                "keywords": st.column_config.TextColumn("Ключевые слова"),
                "content": st.column_config.TextColumn("Содержание (превью)", width="large"),
                "updated_at": st.column_config.TextColumn("Обновлено", width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            edit_id = st.number_input("ID для редактирования/удаления", min_value=1, step=1)

        selected_item = next((x for x in items if x.id == edit_id), None)

        if selected_item:
            with st.form("edit_form"):
                st.write(f"Редактирование ID: {edit_id}")
                edit_title = st.text_input("Название (Title)", value=selected_item.title or "")
                edit_cat = st.text_input("Категория (Category)", value=selected_item.category or "")
                edit_keywords = st.text_input(
                    "Ключевые слова (Keywords)",
                    value=", ".join(selected_item.keywords) if selected_item.keywords else "",
                    placeholder="через запятую",
                )
                edit_content = st.text_area("Содержание", value=selected_item.content)

                # File attachments for this knowledge entry
                async def _get_files_for_link():
                    async with async_session() as session:
                        all_f = await repo.get_all_files(session)
                        linked = await repo.get_linked_files(session, edit_id)
                        return all_f, linked
                _all_files, _linked_files = run_async(_get_files_for_link())
                _linked_ids = [f.id for f in _linked_files]
                _file_options = {
                    f.id: f"#{f.id} [{f.category or '—'}] {f.title or (f.caption or '')[:60]}"
                    for f in _all_files
                }
                picked_file_ids = st.multiselect(
                    "Прикреплённые файлы",
                    options=list(_file_options.keys()),
                    default=_linked_ids,
                    format_func=lambda fid: _file_options.get(fid, str(fid)),
                )

                c_save, c_del = st.columns(2)
                with c_save:
                    save_click = st.form_submit_button("💾 Сохранить изменения")
                with c_del:
                    del_click = st.form_submit_button("🗑 Удалить запись", type="primary")

                if save_click:
                    kw_list = [kw.strip() for kw in edit_keywords.split(",") if kw.strip()] if edit_keywords else None
                    async def save_logic():
                        async with async_session() as session:
                            ok = await repo.update_knowledge(
                                session,
                                edit_id,
                                edit_content,
                                edit_cat or None,
                                edit_title or None,
                                kw_list,
                            )
                            await repo.set_knowledge_files(session, edit_id, picked_file_ids)
                            return ok
                    if run_async(save_logic()):
                        st.success("Обновлено!")
                        st.rerun()
                    else:
                        st.error("Ошибка при обновлении.")

                if del_click:
                    async def del_logic():
                        async with async_session() as session:
                            return await repo.delete_knowledge(session, edit_id)
                    if run_async(del_logic()):
                        st.warning("Удалено!")
                        st.rerun()
                    else:
                        st.error("Ошибка при удалении.")

# PAGE 2: FILES
elif page == "📂 Файлы":
    st.title("Управление Файлами")
    st.write("Просмотр и редактирование индексированных файлов.")

    async def get_files_admin():
        async with async_session() as session:
            return await repo.get_all_files(session)

    files = run_async(get_files_admin())

    if files:
        existing_categories = sorted({f.category for f in files if f.category})
        if existing_categories:
            st.caption(f"Существующие категории: {', '.join(existing_categories)}")

        df_files = pd.DataFrame([
            {
                "id": f.id,
                "title": f.title or "",
                "caption": (f.caption or "")[:80] + ("…" if f.caption and len(f.caption) > 80 else ""),
                "category": f.category or "",
                "keywords": ", ".join(f.keywords) if f.keywords else "",
                "type": f.type or "",
                "updated_at": f.updated_at.strftime("%d.%m.%Y %H:%M") if f.updated_at else "—",
            }
            for f in files
        ])
        st.dataframe(df_files, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            edit_file_id = st.number_input("ID для редактирования/удаления", min_value=1, step=1)

        selected_file = next((f for f in files if f.id == edit_file_id), None)

        if selected_file:
            with st.form("edit_file_form"):
                st.write(f"Редактирование Файла ID: {edit_file_id}")

                curr_caption = selected_file.caption or ""
                curr_category = selected_file.category or ""
                curr_type = selected_file.type or "document"

                edit_title = st.text_input("Название (Title)", value=selected_file.title or "")
                edit_caption = st.text_area("Описание (Caption)", value=curr_caption)
                edit_category = st.text_input("Категория", value=curr_category)
                edit_keywords = st.text_input(
                    "Ключевые слова (через запятую)",
                    value=", ".join(selected_file.keywords) if selected_file.keywords else "",
                )
                edit_type = st.selectbox(
                    "Тип", options=["document", "photo"],
                    index=0 if curr_type == "document" else 1,
                )

                c_save, c_del = st.columns(2)
                with c_save:
                    save_file_click = st.form_submit_button("💾 Сохранить изменения")
                with c_del:
                    del_file_click = st.form_submit_button("🗑 Удалить файл", type="primary")

                if save_file_click:
                    kw_list = [kw.strip() for kw in edit_keywords.split(",") if kw.strip()] or None
                    async def save_file_logic():
                        async with async_session() as session:
                            return await repo.update_file(
                                session, edit_file_id,
                                caption=edit_caption,
                                category=edit_category or None,
                                file_type=edit_type,
                                title=edit_title or None,
                                keywords=kw_list,
                            )
                    if run_async(save_file_logic()):
                        st.success("Файл обновлён! Эмбеддинг пересчитан.")
                        st.rerun()
                    else:
                        st.error("Ошибка при обновлении файла.")

                if del_file_click:
                    async def del_file_logic():
                        async with async_session() as session:
                            return await repo.delete_file(session, edit_file_id)
                    if run_async(del_file_logic()):
                        st.warning("Файл удалён!")
                        st.rerun()
                    else:
                        st.error("Ошибка при удалении файла.")
    else:
        st.info("Файлов нет.")

# PAGE 3: USERS #TODO refactor users selection
elif page == "👥 Пользователи":
    st.title("Пользователи и Квоты")
    
    async def get_users():
        async with async_session() as session:
             from sqlalchemy import select
             from core.models import User
             result = await session.execute(select(User).order_by(User.last_active.desc()).limit(100))
             return result.scalars().all()

    users = run_async(get_users())
    
    if users:
        df_users = pd.DataFrame([
            {
                "ID": u.telegram_id, 
                "username": u.username, 
                "fullname": u.full_name,
                "requests_left": u.requests_left,
                "reset_at": u.quota_reset_at
            }
            for u in users
        ])
        st.dataframe(df_users, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            edit_user_id = st.number_input("Telegram ID пользователя", step=1, format="%d")

        selected_user = next((u for u in users if u.telegram_id == edit_user_id), None)

        if selected_user:
            with st.form("edit_user_form"):
                st.write(f"Редактирование Квоты Пользователя ID: {edit_user_id}")
                
                curr_requests = selected_user.requests_left if selected_user.requests_left is not None else 0
                edit_quota = st.number_input("Осталось запросов (requests_left)", value=curr_requests, step=1)

                save_user_click = st.form_submit_button("💾 Обновить квоту")

                if save_user_click:
                    async def save_user_logic():
                        async with async_session() as session:
                            return await repo.update_user_quota(session, edit_user_id, edit_quota)
                    if run_async(save_user_logic()):
                        st.success("Квота обновлена!")
                        st.rerun()
                    else:
                        st.error("Ошибка при обновлении квоты.")
    else:
        st.info("Пользователей нет.")

# PAGE 4: PLAYGROUND
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

                    # File search diagnostics
                    st.subheader("Файлы (vector search)")
                    from bot.handlers.ai import (
                        _filter_fallback_files,
                        _MAX_FALLBACK_DISTANCE,
                        _MIN_GAP,
                    )
                    file_hits = await repo.search_files(session, query, limit=5)
                    if file_hits:
                        for file_item, dist in file_hits:
                            keywords_hit = [
                                k for k in (file_item.keywords or [])
                                if k.lower() in query.lower()
                            ]
                            cols = st.columns([1, 3, 2])
                            cols[0].metric("Distance", f"{dist:.4f}")
                            cols[1].info(
                                f"**[{file_item.category or '—'}]** "
                                f"{file_item.title or file_item.caption or '(no description)'}"
                            )
                            cols[2].write(
                                f"✅ kw: {keywords_hit}" if keywords_hit else "⛔ no keyword match"
                            )

                        # Show the real filter decision (same logic the bot uses)
                        kw_matched = [
                            (f, d) for f, d in file_hits
                            if (f.keywords or [])
                            and any(k.lower() in query.lower() for k in f.keywords)
                        ]
                        selected = _filter_fallback_files(file_hits, query)
                        if selected:
                            f = selected[0]
                            st.success(
                                f"🎯 Filter selects: **#{f.id} {f.title or f.caption}** "
                                f"(dist ≤ {_MAX_FALLBACK_DISTANCE})"
                            )
                        else:
                            reasons = []
                            if not kw_matched:
                                reasons.append("no file has a keyword in the query")
                            else:
                                top_f, top_d = kw_matched[0]
                                if top_d > _MAX_FALLBACK_DISTANCE:
                                    reasons.append(
                                        f"top keyword-match distance {top_d:.4f} > {_MAX_FALLBACK_DISTANCE}"
                                    )
                                if len(kw_matched) > 1:
                                    _, sd = kw_matched[1]
                                    gap = sd - top_d
                                    if gap < _MIN_GAP:
                                        reasons.append(
                                            f"gap among kw-matched files {gap:.4f} < {_MIN_GAP}"
                                        )
                            st.warning(
                                "⛔ Filter rejects all candidates — "
                                + "; ".join(reasons or ["(unknown)"])
                            )
                    else:
                        st.info("Файлы не найдены.")

                    st.write("🤖 Генерация ответа AI...")
                    response = await get_ai_answer(query, context)
                    return response
            
            ai_resp = run_async(test_logic())
            
            st.subheader("Ответ AI:")
            st.success(ai_resp)

# PAGE 5: SCHEDULE VIEWER
elif page == "📅 Расписание":
    st.title("Просмотр Расписания WSP")

    # --- Data Fetchers ---
    async def get_subjects():
        async with async_session() as session:
            stmt = select(Subject).where(Subject.events.any()).order_by(Subject.code)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_instructors():
        async with async_session() as session:
            stmt = select(Instructor).where(Instructor.events.any()).order_by(Instructor.full_name)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_rooms():
        async with async_session() as session:
            stmt = select(Room).where(Room.events.any()).order_by(Room.number)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_schedule_by_subject(subject_id: int):
        async with async_session() as session:
            stmt = (
                select(ScheduleEvent)
                .where(ScheduleEvent.subject_id == subject_id)
                .options(
                    selectinload(ScheduleEvent.instructor),
                    selectinload(ScheduleEvent.room)
                )
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_schedule_by_instructor(instructor_id: int):
        async with async_session() as session:
            stmt = (
                select(ScheduleEvent)
                .where(ScheduleEvent.instructor_id == instructor_id)
                .options(
                    selectinload(ScheduleEvent.subject),
                    selectinload(ScheduleEvent.room)
                )
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_schedule_by_room(room_id: int):
        async with async_session() as session:
            stmt = (
                select(ScheduleEvent)
                .where(ScheduleEvent.room_id == room_id)
                .options(
                    selectinload(ScheduleEvent.subject),
                    selectinload(ScheduleEvent.instructor)
                )
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    # --- UI Tabs ---
    tab_subj, tab_inst, tab_room = st.tabs(["📚 По предметам", "👨‍🏫 По преподавателям", "🚪 По аудиториям"])

    day_sort_map = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 7}

    def format_time(e):
        return f"{e.start_time.strftime('%H:%M')} - {e.end_time.strftime('%H:%M')}"

    # TAB 1: SUBJECTS
    with tab_subj:
        subjects = run_async(get_subjects())
        if not subjects:
            st.warning("Нет предметов с расписанием.")
        else:
            df_subj = pd.DataFrame([
                {
                    "id": s.id,
                    "Code": s.code,
                    "Name (EN)": s.name_en or "",
                    "Name (RU)": s.name_ru or "",
                    "Name (KZ)": s.name_kz or "",
                    "Department": s.department or "",
                    "Credits": s.credits or "",
                    "Formula": s.formula or "",
                    "Year": s.year or "",
                    "Period": s.period or ""
                } for s in subjects
            ])

            st.write("Выберите предмет из списка (одна строка):")
            sel_subj = st.dataframe(
                df_subj,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={"id": None}
            )

            if sel_subj.selection.rows:
                selected_idx = sel_subj.selection.rows[0]
                selected_id = int(df_subj.iloc[selected_idx]['id'])
                
                events = run_async(get_schedule_by_subject(selected_id))
                if events:
                    data = []
                    for e in events:
                        data.append({
                            "День": e.day_of_week.value,
                            "Время": format_time(e),
                            "Тип": e.lesson_type.value,
                            "Преподаватель": e.instructor.full_name if e.instructor else "—",
                            "Кабинет": e.room.number if e.room else "—",
                            "Вместимость": e.group_info or "",
                            "day_num": day_sort_map.get(e.day_of_week.value, 8)
                        })
                    
                    df_events = pd.DataFrame(data).sort_values(by=["day_num", "Время"]).drop(columns=["day_num"])
                    st.subheader("Расписание предмета")
                    st.dataframe(df_events, use_container_width=True, hide_index=True)
                else:
                    st.info("Для этого предмета нет событий.")

    # TAB 2: INSTRUCTORS
    with tab_inst:
        instructors = run_async(get_instructors())
        if not instructors:
            st.warning("Нет преподавателей с расписанием.")
        else:
            df_inst = pd.DataFrame([
                {
                    "id": i.id,
                    "ФИО Преподавателя": i.full_name
                } for i in instructors
            ])

            st.write("Выберите преподавателя:")
            sel_inst = st.dataframe(
                df_inst,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={"id": None}
            )

            if sel_inst.selection.rows:
                selected_idx = sel_inst.selection.rows[0]
                selected_id = int(df_inst.iloc[selected_idx]['id'])
                
                events = run_async(get_schedule_by_instructor(selected_id))
                if events:
                    data = []
                    for e in events:
                        subj_desc = f"{e.subject.code} - {e.subject.name_en or e.subject.name_ru or ''}" if e.subject else "—"
                        data.append({
                            "День": e.day_of_week.value,
                            "Время": format_time(e),
                            "Предмет": subj_desc,
                            "Тип": e.lesson_type.value,
                            "Кабинет": e.room.number if e.room else "—",
                            "Вместимость": e.group_info or "",
                            "day_num": day_sort_map.get(e.day_of_week.value, 8)
                        })
                    
                    df_events = pd.DataFrame(data).sort_values(by=["day_num", "Время"]).drop(columns=["day_num"])
                    st.subheader("Расписание преподавателя")
                    st.dataframe(df_events, use_container_width=True, hide_index=True)
                else:
                    st.info("Для этого преподавателя нет событий.")

    # TAB 3: ROOMS
    with tab_room:
        rooms = run_async(get_rooms())
        if not rooms:
            st.warning("Нет аудиторий с расписанием.")
        else:
            df_room = pd.DataFrame([
                {
                    "id": r.id,
                    "Аудитория": r.number
                } for r in rooms
            ])

            st.write("Выберите аудиторию:")
            sel_room = st.dataframe(
                df_room,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={"id": None}
            )

            if sel_room.selection.rows:
                selected_idx = sel_room.selection.rows[0]
                selected_id = int(df_room.iloc[selected_idx]['id'])
                
                events = run_async(get_schedule_by_room(selected_id))
                if events:
                    data = []
                    for e in events:
                        subj_desc = f"{e.subject.code} - {e.subject.name_en or e.subject.name_ru or ''}" if e.subject else "—"
                        data.append({
                            "День": e.day_of_week.value,
                            "Время": format_time(e),
                            "Предмет": subj_desc,
                            "Тип": e.lesson_type.value,
                            "Преподаватель": e.instructor.full_name if e.instructor else "—",
                            "Вместимость": e.group_info or "",
                            "day_num": day_sort_map.get(e.day_of_week.value, 8)
                        })
                    
                    df_events = pd.DataFrame(data).sort_values(by=["day_num", "Время"]).drop(columns=["day_num"])
                    st.subheader("Расписание аудитории")
                    st.dataframe(df_events, use_container_width=True, hide_index=True)
                else:
                    st.info("В этой аудитории нет событий.")

# PAGE 6: ANALYTICS & FEEDBACK (RLHF)
elif page == "💬 Обратная связь":
    st.title("Обратная связь (RLHF)")

    async def get_interaction_logs():
        async with async_session() as session:
            stmt = select(InteractionLog).order_by(InteractionLog.created_at.desc()).limit(1000)
            result = await session.execute(stmt)
            return result.scalars().all()

    logs = run_async(get_interaction_logs())

    if not logs:
        st.info("Записей пока нет.")
    else:
        df = pd.DataFrame([
            {
                "id": l.id,
                "created_at": l.created_at,
                "telegram_id": l.telegram_id,
                "user_query": l.user_query,
                "bot_response": l.bot_response,
                "feedback": l.feedback,
            } for l in logs
        ])

        total = len(df)
        likes = int((df["feedback"] == 1).sum())
        dislikes = int((df["feedback"] == -1).sum())
        no_feedback = int((df["feedback"] == 0).sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Всего запросов", total)
        c2.metric("👍 Лайков", likes)
        c3.metric("👎 Дизлайков", dislikes)
        c4.metric("🤷\u200d♂️ Без оценки", no_feedback)

        st.divider()
        st.subheader("Журнал дизлайков")

        df_dislikes = df[df["feedback"] == -1].copy()

        if df_dislikes.empty:
            st.success("Дизлайков пока нет!")
        else:
            df_dislikes["created_at"] = pd.to_datetime(df_dislikes["created_at"]).dt.strftime("%d.%m.%Y %H:%M")
            st.dataframe(
                df_dislikes[["created_at", "user_query", "bot_response"]].rename(
                    columns={"created_at": "Дата", "user_query": "Вопрос", "bot_response": "Ответ бота"}
                ),
                use_container_width=True,
                hide_index=True,
            )

