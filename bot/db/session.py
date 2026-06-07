from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from bot.config import settings
from bot.db.url import normalize_db_url

_db_url = normalize_db_url(settings.database_url)

# connect_args timeout only applies to asyncpg; SQLite ignores unknown args, so
# guard it to the Postgres driver to avoid passing it to aiosqlite.
_connect_args = {"timeout": 10} if "asyncpg" in _db_url else {}
engine = create_async_engine(_db_url, echo=False, connect_args=_connect_args)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
