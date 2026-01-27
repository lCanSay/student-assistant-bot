from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import KnowledgeItem, FileItem, User
from services.embeddings import get_vector

async def add_knowledge(session: AsyncSession, content: str, category: str, keywords: list[str] = None):
    # Check if exists to avoid duplicates
    stmt = select(KnowledgeItem).where(KnowledgeItem.content == content)
    result = await session.execute(stmt)
    if result.scalars().first():
        return

    # Construct enriched string for embedding (E5 format)
    # get_vector adds "passage: " prefix automatically
    keywords_str = ", ".join(keywords) if keywords else ""
    enriched_text = f"Topic: {category}. Keywords: {keywords_str}. Content: {content}"
    
    vector = get_vector(enriched_text, is_query=False)
    
    # Save original clean content to DB
    item = KnowledgeItem(content=content, category=category, embedding=vector)
    session.add(item)
    await session.commit()

async def add_file(session: AsyncSession, file_id: str, caption: str, keywords: list[str], file_type: str):
    vector = get_vector(caption, is_query=False)
    
    # Check if exists
    stmt = select(FileItem).where(FileItem.file_id == file_id)
    result = await session.execute(stmt)
    existing_item = result.scalar_one_or_none()
    
    if existing_item:
        # Update existing
        existing_item.caption = caption
        existing_item.keywords = keywords
        existing_item.type = file_type
        existing_item.embedding = vector
    else:
        # Create new
        item = FileItem(
            file_id=file_id,
            caption=caption,
            keywords=keywords,
            type=file_type,
            embedding=vector
        )
        session.add(item)
    
    await session.commit()

async def search_knowledge(session: AsyncSession, query: str, limit: int = 3):
    query_vector = get_vector(query, is_query=True)
    # Using cosine distance operator <=>
    stmt = select(KnowledgeItem).order_by(KnowledgeItem.embedding.cosine_distance(query_vector)).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()

async def search_files(session: AsyncSession, query: str, limit: int = 3):
    query_vector = get_vector(query, is_query=True)
    stmt = select(FileItem).order_by(FileItem.embedding.cosine_distance(query_vector)).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str, username: str):
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(telegram_id=telegram_id, full_name=full_name, username=username)
        session.add(user)
        await session.commit()
    return user
