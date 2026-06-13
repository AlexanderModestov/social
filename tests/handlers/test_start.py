import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.handlers._fakes import FakeMessage, fake_session_factory


@pytest.mark.asyncio
async def test_start_hides_button_when_all_channels_have_tov():
    from bot.handlers import start
    from bot.db.channels import CHANNELS
    message = FakeMessage()
    fake_user_repo = MagicMock(); fake_user_repo.get_or_create = AsyncMock()
    fake_tov_repo = MagicMock(); fake_tov_repo.get_channels_with_tov = AsyncMock(return_value=set(CHANNELS))
    with patch.object(start, "UserRepository", return_value=fake_user_repo), \
         patch.object(start, "ToneOfVoiceRepository", return_value=fake_tov_repo), \
         patch.object(start, "async_session_factory", fake_session_factory()):
        await start.cmd_start(message)
    kb = message.answer.await_args.kwargs["reply_markup"]
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert not any("tone of voice" in t.lower() for t in labels)


@pytest.mark.asyncio
async def test_start_shows_button_when_no_channels_have_tov():
    from bot.handlers import start
    message = FakeMessage()
    fake_user_repo = MagicMock(); fake_user_repo.get_or_create = AsyncMock()
    fake_tov_repo = MagicMock(); fake_tov_repo.get_channels_with_tov = AsyncMock(return_value=set())
    with patch.object(start, "UserRepository", return_value=fake_user_repo), \
         patch.object(start, "ToneOfVoiceRepository", return_value=fake_tov_repo), \
         patch.object(start, "async_session_factory", fake_session_factory()):
        await start.cmd_start(message)
    kb = message.answer.await_args.kwargs["reply_markup"]
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("tone of voice" in t.lower() for t in labels)
