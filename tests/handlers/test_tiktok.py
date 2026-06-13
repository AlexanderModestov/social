import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import tiktok
from bot.db.channels import TIKTOK
from tests.handlers._fakes import FakeMessage, FakeCallback, FakeFSMContext, fake_session_factory


@pytest.mark.asyncio
async def test_caption_uses_tiktok_channel():
    state = FakeFSMContext({"recorded_url": "http://x"})
    callback = FakeCallback(data="demo:caption")

    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)

    with patch.object(tiktok, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tiktok, "async_session_factory", fake_session_factory()), \
         patch.object(tiktok, "ScraperService") as Scr, \
         patch.object(tiktok, "ClaudeService") as Cl:
        Scr.return_value.scrape_url = AsyncMock(return_value="page")
        Cl.return_value.generate_tiktok_caption = AsyncMock(return_value="CAP")
        await tiktok.on_generate_caption(callback, state)

    fake_repo.get_for_channel.assert_awaited_with(callback.from_user.id, TIKTOK)
