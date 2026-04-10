from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import Sequence
from core.models import KnowledgeItem, FileItem, User, InteractionLog

from services.embeddings import get_vector, build_enriched_text


async def add_knowledge(
    session: AsyncSession,
    content: str,
    category: str | None = None,
    title: str | None = None,
    keywords: list[str] | None = None,
):
    stmt = select(KnowledgeItem).where(KnowledgeItem.content == content)
    result = await session.execute(stmt)
    if result.scalars().first():
        return

    enriched_text = build_enriched_text(content, title, category, keywords)
    vector = get_vector(enriched_text, is_query=False)

    item = KnowledgeItem(
        content=content,
        category=category,
        title=title,
        keywords=keywords,
        embedding=vector,
    )
    session.add(item)
    await session.commit()


async def get_all_knowledge(session: AsyncSession, limit: int = 200) -> Sequence[KnowledgeItem]:
    stmt = select(KnowledgeItem).order_by(KnowledgeItem.id.desc()).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_knowledge(
    session: AsyncSession,
    item_id: int,
    new_content: str,
    new_category: str | None = None,
    new_title: str | None = None,
    new_keywords: list[str] | None = None,
) -> bool:
    enriched_text = build_enriched_text(new_content, new_title, new_category, new_keywords)
    vector = get_vector(enriched_text, is_query=False)

    stmt = (
        update(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .values(
            content=new_content,
            category=new_category,
            title=new_title,
            keywords=new_keywords,
            embedding=vector,
            updated_at=func.now(),  # explicit: Core update() doesn't trigger onupdate
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def delete_knowledge(session: AsyncSession, item_id: int) -> bool:
    stmt = delete(KnowledgeItem).where(KnowledgeItem.id == item_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def upsert_file(
    session: AsyncSession,
    file_id: str,
    file_unique_id: str,
    file_name: str,
    caption: str,
    file_type: str,
    category: str | None = None,
):
    clean_caption = caption or ""
    embedding_text = f"Filename: {file_name}. Description: {clean_caption}"
    vector = get_vector(embedding_text, is_query=False)

    stmt = select(FileItem).where(FileItem.file_unique_id == file_unique_id)
    result = await session.execute(stmt)
    existing_item = result.scalar_one_or_none()

    if existing_item:
        existing_item.file_id = file_id
        existing_item.caption = clean_caption
        existing_item.type = file_type
        existing_item.embedding = vector
        if category is not None:
            existing_item.category = category
    else:
        item = FileItem(
            file_id=file_id,
            file_unique_id=file_unique_id,
            caption=clean_caption,
            type=file_type,
            embedding=vector,
            category=category,
        )
        session.add(item)

    await session.commit()


async def update_file(
    session: AsyncSession, item_id: int, caption: str, category: str, file_type: str
) -> bool:
    stmt = (
        update(FileItem)
        .where(FileItem.id == item_id)
        .values(caption=caption, category=category, type=file_type)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def delete_file(session: AsyncSession, item_id: int) -> bool:
    stmt = delete(FileItem).where(FileItem.id == item_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def get_files_by_category(session: AsyncSession, category: str) -> list[FileItem]:
    """Fetch all files that belong to a given category."""
    stmt = select(FileItem).where(FileItem.category == category)
    result = await session.execute(stmt)
    return result.scalars().all()


async def search_knowledge(session: AsyncSession, query: str, limit: int = 3):
    query_vector = get_vector(query, is_query=True)
    distance_col = KnowledgeItem.embedding.cosine_distance(query_vector).label("distance")
    stmt = select(KnowledgeItem, distance_col).order_by(distance_col).limit(limit)
    result = await session.execute(stmt)
    return result.all()


async def search_files(session: AsyncSession, query: str, limit: int = 3):
    query_vector = get_vector(query, is_query=True)
    distance_col = FileItem.embedding.cosine_distance(query_vector).label("distance")
    stmt = select(FileItem, distance_col).order_by(distance_col).limit(limit)
    result = await session.execute(stmt)
    return result.all()


async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str, username: str):
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=telegram_id, full_name=full_name, username=username)
        session.add(user)
    else:
        user.full_name = full_name
        user.username = username
        user.last_active = func.now()

    await session.commit()
    return user


async def update_user_quota(
    session: AsyncSession, telegram_id: int, requests_left: int
) -> bool:
    stmt = (
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=requests_left)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def check_and_increment_quota(session: AsyncSession, user: User, limit: int = None) -> bool:
    if limit is None:
        from config import DAILY_LIMIT
        limit = DAILY_LIMIT

    await session.refresh(user)

    now = datetime.now(timezone.utc)

    if user.quota_reset_at and now > user.quota_reset_at:
        user.requests_left = limit
        user.quota_reset_at = now + timedelta(hours=24)

    if user.quota_reset_at is None:
        user.requests_left = limit
        user.quota_reset_at = now + timedelta(hours=24)

    if user.requests_left > 0:
        user.requests_left -= 1
        await session.commit()
        return True
    else:
        return False


async def log_interaction(
    session: AsyncSession, telegram_id: int, user_query: str, bot_response: str
) -> int:
    """Insert an interaction record and return its ID."""
    log = InteractionLog(
        telegram_id=telegram_id,
        user_query=user_query,
        bot_response=bot_response,
    )
    session.add(log)
    await session.flush()
    interaction_id = log.id
    await session.commit()
    return interaction_id


async def update_feedback(
    session: AsyncSession, interaction_id: int, feedback_value: int
) -> None:
    """Update the feedback field for a given interaction."""
    stmt = (
        update(InteractionLog)
        .where(InteractionLog.id == interaction_id)
        .values(feedback=feedback_value)
    )
    await session.execute(stmt)
    await session.commit()
