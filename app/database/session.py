from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Engine setup using psycopg
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

# Session factory for generating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Async engine setup
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine
)

async def get_db():
    """
    FastAPI dependency to provide a database session.
    """
    async with AsyncSessionLocal() as db:
        yield db

