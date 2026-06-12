import pytest
from unittest.mock import patch
from bot.handlers.linkedin import _shared


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


def test_approval_card_has_charcount_and_keyboard():
    card = _shared.approval_card("Hello world")
    assert "11 chars" in card["text"]
    assert card["reply_markup"] is not None
