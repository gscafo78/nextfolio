from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def celery_db_session():
    """
    Sessione DB per i worker Celery.
    Crea un engine NullPool fresco per ogni invocazione per evitare
    conflitti asyncpg dopo il fork (prefork pool di Celery).
    """
    _engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(_engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await _engine.dispose()
