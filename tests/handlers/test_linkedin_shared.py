import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers.linkedin import _shared
from bot.db.channels import LINKEDIN
from tests.handlers._fakes import fake_session_factory


@pytest.mark.asyncio
async def test_resolve_source_uses_apify_when_url_and_token(monkeypatch):
    monkeypatch.setattr(_shared.settings, "apify_token", "tok", raising=False)
    with patch.object(_shared, "fetch_post", return_value={"text": "POST BODY"}) as fp:
        text, used = await _shared.resolve_source(
            "https://www.linkedin.com/posts/x-activity-7448808898326654978-AA"
        )
    assert "POST BODY" in text
    assert used == "apify"
    fp.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_source_asks_paste_when_no_url():
    text, used = await _shared.resolve_source("just some pasted text")
    assert text == "just some pasted text"
    assert used == "paste"


@pytest.mark.asyncio
async def test_resolve_source_url_without_token_needs_paste(monkeypatch):
    monkeypatch.setattr(_shared.settings, "apify_token", None, raising=False)
    text, used = await _shared.resolve_source(
        "https://www.linkedin.com/posts/x-activity-7448808898326654978-AA"
    )
    assert used == "needs_paste"
    assert text == ""


@pytest.mark.asyncio
async def test_resolve_source_apify_empty_falls_through_to_needs_paste(monkeypatch):
    monkeypatch.setattr(_shared.settings, "apify_token", "tok", raising=False)
    with patch.object(_shared, "fetch_post", return_value=None) as fp:
        text, used = await _shared.resolve_source(
            "https://www.linkedin.com/posts/x-activity-7448808898326654978-AA"
        )
    assert used == "needs_paste"
    assert text == ""
    fp.assert_called_once()


def test_approval_card_has_charcount_and_keyboard():
    card = _shared.approval_card("Hello world")
    assert "11 chars" in card["text"]
    assert card["reply_markup"] is not None


def test_report_card_has_save_button_and_extra_rows():
    from aiogram.types import InlineKeyboardButton
    extra = [[InlineKeyboardButton(text="X", callback_data="x:y")]]
    card = _shared.report_card("hello", extra_rows=extra)
    assert card["text"] == "hello"
    data = [b.callback_data for row in card["reply_markup"].inline_keyboard for b in row]
    assert "x:y" in data          # extra row present
    assert "skill:save" in data   # save button appended
    # extra row comes before save
    assert data.index("x:y") < data.index("skill:save")


@pytest.mark.asyncio
async def test_get_active_tov_uses_linkedin_channel():
    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=MagicMock(profile_json={"x": 1}))
    with patch.object(_shared, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(_shared, "async_session_factory", fake_session_factory()):
        result = await _shared.get_active_tov(42)
    fake_repo.get_for_channel.assert_awaited_once_with(42, LINKEDIN)
    assert result == {"x": 1}


@pytest.mark.asyncio
async def test_get_active_tov_returns_empty_when_none():
    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(_shared, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(_shared, "async_session_factory", fake_session_factory()):
        result = await _shared.get_active_tov(42)
    assert result == {}
