from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,         # keep 20 connections ready
    max_overflow=10,      # allow 10 more under burst
    pool_timeout=30,      # wait up to 30 s for a free connection
    pool_recycle=1800,    # recycle connections every 30 min
    pool_pre_ping=True,   # verify connections before use
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session
