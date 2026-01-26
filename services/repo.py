from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import KnowledgeItem, FileItem, User
from services.embeddings import embeddings_service

class Repo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_knowledge(self, content: str, category: str):
        # Check if exists to avoid duplicates
        stmt = select(KnowledgeItem).where(KnowledgeItem.content == content)
        result = await self.session.execute(stmt)
        if result.scalars().first():
            return

        vector = embeddings_service.get_vector(content, is_query=False)
        item = KnowledgeItem(content=content, category=category, embedding=vector)
        self.session.add(item)
        await self.session.commit()

    async def add_file(self, file_id: str, caption: str, keywords: list[str], file_type: str):
        vector = embeddings_service.get_vector(caption, is_query=False)
        
        # Check if exists
        stmt = select(FileItem).where(FileItem.file_id == file_id)
        result = await self.session.execute(stmt)
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
            self.session.add(item)
        
        await self.session.commit()

    async def search_knowledge(self, query: str, limit: int = 3):
        query_vector = embeddings_service.get_vector(query, is_query=True)
        # Using cosine distance operator <=>
        stmt = select(KnowledgeItem).order_by(KnowledgeItem.embedding.cosine_distance(query_vector)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_files(self, query: str, limit: int = 3):
        query_vector = embeddings_service.get_vector(query, is_query=True)
        stmt = select(FileItem).order_by(FileItem.embedding.cosine_distance(query_vector)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_or_create_user(self, telegram_id: int, full_name: str, username: str):
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(telegram_id=telegram_id, full_name=full_name, username=username)
            self.session.add(user)
            await self.session.commit()
        return user
