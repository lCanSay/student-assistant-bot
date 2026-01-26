from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from pgvector.sqlalchemy import Vector
from core.database import Base

class KnowledgeItem(Base):
    __tablename__ = 'knowledge_base'

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    category = Column(String)
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FileItem(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    file_id = Column(String, unique=True, nullable=False)
    caption = Column(Text)
    keywords = Column(ARRAY(String))
    type = Column(String) # 'document' or 'photo'
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True)
    full_name = Column(String)
    username = Column(String)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), onupdate=func.now())
