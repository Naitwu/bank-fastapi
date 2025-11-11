from typing import AsyncGenerator
import asyncio

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text
from sqlalchemy.pool import AsyncAdaptedQueuePool

logger = get_logger()

engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
    )


async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = async_session()
    try:
        yield session
    except Exception as e:
        logger.error(f"DB Session error: {e}")
        if session:
            try:
                await session.rollback()
                logger.info("successfully rolled back the session due to error.")
            except Exception as rollback_error:
                logger.error(f"Error during session rollback: {rollback_error}")
        raise
    finally:
        if session:
            try:
                await session.close()
                logger.debug("DB Session closed successfully.")
            except Exception as close_error:
                logger.error(f"Error closing DB session: {close_error}")


async def init_db() -> None:
    try:
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("Database connection established successfully.")
                break
            except Exception as conn_error:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to connect to the database after {max_retries} attempts: {conn_error}"
                    )
                    raise
                logger.warning(
                    f"Database connection attempt {attempt + 1}"
                )
                await asyncio.sleep(retry_delay*(attempt + 1))

    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise