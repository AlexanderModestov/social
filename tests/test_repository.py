import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.db.repository import UserRepository, ToneOfVoiceRepository


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = UserRepository(session)
    user = await repo.get_or_create(telegram_id=123, username="alex")

    assert user.telegram_id == 123
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing():
    from bot.db.models import User
    existing = User(telegram_id=123, username="alex")
    session = AsyncMock()
    session.get = AsyncMock(return_value=existing)

    repo = UserRepository(session)
    user = await repo.get_or_create(telegram_id=123, username="alex")

    assert user is existing
    session.add.assert_not_called()
