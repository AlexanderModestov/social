import asyncio
import os
import sys
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from bot.db.models import Base
from bot.db.url import normalize_db_url

config = context.config
# Railway supplies postgres:// or postgresql:// (sometimes with libpq-only query
# params); asyncpg needs postgresql+asyncpg:// and rejects those params.
_db_url = normalize_db_url(os.environ["DATABASE_URL"])
config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# asyncpg connect timeout: without this, an unreachable DB host (e.g. a private
# Railway hostname before the network is up, or a wrong DATABASE_URL) makes the
# migration hang silently instead of failing. 10s + a few retries fixes that.
_CONNECT_TIMEOUT = 10
_MAX_ATTEMPTS = 5

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    safe_url = _db_url.split("@")[-1] if "@" in _db_url else _db_url
    print(f"[alembic] connecting to DB host: {safe_url}", flush=True)
    connectable = create_async_engine(
        _db_url,
        poolclass=pool.NullPool,
        connect_args={"timeout": _CONNECT_TIMEOUT},
    )
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with connectable.connect() as connection:
                await connection.run_sync(do_run_migrations)
            await connectable.dispose()
            print("[alembic] migrations applied", flush=True)
            return
        except Exception as exc:  # surface the real error instead of hanging
            last_exc = exc
            print(
                f"[alembic] DB connect attempt {attempt}/{_MAX_ATTEMPTS} failed: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(3)
    await connectable.dispose()
    print("[alembic] giving up — could not reach the database", file=sys.stderr, flush=True)
    raise SystemExit(1) from last_exc

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

run_migrations_online()
