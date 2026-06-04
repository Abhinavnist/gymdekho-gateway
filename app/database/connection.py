import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
from psycopg_pool import AsyncConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)

# Global connection pool — created once on startup, shared across all requests
_pool: AsyncConnectionPool | None = None


async def create_pool() -> None:
    global _pool
    conninfo = (
        f"host={settings.db_host} "
        f"port={settings.db_port} "
        f"dbname={settings.db_name} "
        f"user={settings.db_user} "
        f"password={settings.db_password}"
    )
    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=settings.db_min_connections,
        max_size=settings.db_max_connections,
        kwargs={"autocommit": False, "row_factory": psycopg.rows.dict_row},
        open=False,
    )
    await _pool.open()
    await _pool.wait()
    logger.info("Database connection pool created.")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        logger.info("Database connection pool closed.")


@asynccontextmanager
async def get_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Yield a single connection from the pool. Use for transactions."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Call create_pool() first.")
    async with _pool.connection() as conn:
        yield conn


async def get_db() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """FastAPI dependency — yields a DB connection per request."""
    async with get_connection() as conn:
        yield conn
