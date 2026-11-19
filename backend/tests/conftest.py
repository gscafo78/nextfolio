"""Configurazione comune dei test.

pytest-asyncio crea un event loop per test: un pool di connessioni condiviso
porterebbe connessioni asyncpg legate a un loop già chiuso ("attached to a
different loop"). Nei test si usa quindi NullPool (una connessione per sessione).
"""
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core import database
from app.core.config import settings

database.engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
database.AsyncSessionLocal.configure(bind=database.engine)
