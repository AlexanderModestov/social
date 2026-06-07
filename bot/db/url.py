"""Database URL normalization shared by the runtime engine and Alembic.

Railway / Heroku hand out URLs like ``postgres://`` or ``postgresql://`` and
sometimes append libpq-only query params (``sslmode``, ``channel_binding``,
``sslrootcert``). The ``asyncpg`` driver does not understand those params and
fails at connect time — which, because migrations run before the bot starts,
shows up as a silent startup with no logs. Normalize in one place.
"""
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Query params understood by libpq/psycopg but NOT by asyncpg's connect().
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "sslrootcert", "sslcert", "sslkey"}


def normalize_db_url(url: str) -> str:
    """Return a URL the asyncpg dialect can consume.

    - Coerces ``postgres://`` / ``postgresql://`` to ``postgresql+asyncpg://``.
    - Drops libpq-only query params (asyncpg rejects them).
    - Leaves non-Postgres URLs (e.g. ``sqlite+aiosqlite://``) untouched.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    if "postgresql+asyncpg" not in url:
        return url

    parts = urlsplit(url)
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in _LIBPQ_ONLY_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(kept)))
