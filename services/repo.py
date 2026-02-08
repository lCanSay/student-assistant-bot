from sqlalchemy import select, update, delete, func 
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from core.models import KnowledgeItem, FileItem, User
from services.embeddings import get_vector

async def add_knowledge(session: AsyncSession, content: str, category: str, keywords: list[str] = None):
    stmt = select(KnowledgeItem).where(KnowledgeItem.content == content)
    result = await session.execute(stmt)
    if result.scalars().first():
        return

    # Construct string for embedding (E5 format), concat with keywords
    keywords_str = ", ".join(keywords) if keywords else ""
    enriched_text = f"Topic: {category}. Keywords: {keywords_str}. Content: {content}"
    
    vector = get_vector(enriched_text, is_query=False)
    
    # Save original clean content to DB
    item = KnowledgeItem(content=content, category=category, embedding=vector)
    session.add(item)
    await session.commit()

async def get_all_knowledge(session: AsyncSession, limit: int = 200) -> list[KnowledgeItem]:
    stmt = select(KnowledgeItem).order_by(KnowledgeItem.id.desc()).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()

async def update_knowledge(session: AsyncSession, item_id: int, new_content: str, new_category: str) -> bool:
    enriched_text = f"Topic: {new_category}. Content: {new_content}"
    vector = get_vector(enriched_text, is_query=False)
    
    stmt = (
        update(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .values(content=new_content, category=new_category, embedding=vector)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0

async def delete_knowledge(session: AsyncSession, item_id: int) -> bool:
    stmt = delete(KnowledgeItem).where(KnowledgeItem.id == item_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0

async def upsert_file(session: AsyncSession, file_id: str, file_unique_id: str, file_name: str, caption: str, file_type: str):
    
    clean_caption = caption or ""
    embedding_text = f"Filename: {file_name}. Description: {clean_caption}"
    vector = get_vector(embedding_text, is_query=False)
    
    # Check if exists by unique_id
    stmt = select(FileItem).where(FileItem.file_unique_id == file_unique_id)
    result = await session.execute(stmt)
    existing_item = result.scalar_one_or_none()
    
    if existing_item:
        existing_item.file_id = file_id
        existing_item.caption = clean_caption
        existing_item.type = file_type
        existing_item.embedding = vector
    else:
        item = FileItem(
            file_id=file_id,
            file_unique_id=file_unique_id,
            caption=clean_caption,
            type=file_type,
            embedding=vector
        )
        session.add(item)
    
    await session.commit()

async def search_knowledge(session: AsyncSession, query: str, limit: int = 3):
    query_vector = get_vector(query, is_query=True)
    # Return both Item and distance
    distance_col = KnowledgeItem.embedding.cosine_distance(query_vector).label("distance")
    stmt = select(KnowledgeItem, distance_col).order_by(distance_col).limit(limit)
    result = await session.execute(stmt)
    return result.all()

async def search_files(session: AsyncSession, query: str, limit: int = 3):
    query_vector = get_vector(query, is_query=True)
    # Return both FileItem and distance
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

async def check_and_increment_quota(session: AsyncSession, user: User, limit: int = 5) -> bool:
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
