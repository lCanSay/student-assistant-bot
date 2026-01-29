import asyncio
import json
from sqlalchemy import text
from core.database import engine, Base, async_session
from core.models import KnowledgeItem, FileItem, User
import services.repo as repo
from config import FAQ_FILE, FILES_FILE

async def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: File {path} not found.")
        return []

async def init_db():
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

    print("Migrating data from JSON...")
    async with async_session() as session:
        # 1. Migrate Knowledge Base (FAQ)
        faq_data = await load_json(FAQ_FILE)
        print(f"Loading {len(faq_data)} FAQ items...")
        for item in faq_data:
            content = item.get("text") or item.get("answer") or item.get("content")
            topic = item.get("topic") or "General"
            keywords = item.get("keywords") or []
            
            if content:
                await repo.add_knowledge(session, content=content, category=topic, keywords=keywords)
        
        # 2. Migrate Files
        files_data = await load_json(FILES_FILE)
        print(f"Loading {len(files_data)} files...")
        for item in files_data:
            file_id = item.get("file_id")
            caption = item.get("caption") or ""
            keywords = item.get("keywords") or []
            file_type = item.get("type") or "document"
            
            if file_id:
                await repo.add_file(session, file_id, caption, keywords, file_type)

    print("Migration Complete!")

if __name__ == "__main__":
    asyncio.run(init_db())
