import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.middlewares.access import AccessControlMiddleware


def _event(with_message=True):
    message = SimpleNamespace(answer=AsyncMock()) if with_message else None
    callback = None if with_message else SimpleNamespace(answer=AsyncMock())
    return SimpleNamespace(message=message, callback_query=callback)


@pytest.mark.asyncio
async def test_allowed_user_passes_through():
    mw = AccessControlMiddleware({123})
    handler = AsyncMock(return_value="ok")
    event = _event()
    result = await mw(handler, event, {"event_from_user": SimpleNamespace(id=123)})
    handler.assert_awaited_once()
    assert result == "ok"
    event.message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocked_user_gets_denied_and_handler_not_called():
    mw = AccessControlMiddleware({123})
    handler = AsyncMock()
    event = _event()
    await mw(handler, event, {"event_from_user": SimpleNamespace(id=999)})
    handler.assert_not_awaited()
    event.message.answer.assert_awaited_once()
    assert "access" in event.message.answer.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_empty_allowlist_blocks_everyone():
    mw = AccessControlMiddleware(set())
    handler = AsyncMock()
    event = _event()
    await mw(handler, event, {"event_from_user": SimpleNamespace(id=123)})
    handler.assert_not_awaited()
    event.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_blocked_callback_answered_with_alert():
    mw = AccessControlMiddleware({123})
    handler = AsyncMock()
    event = _event(with_message=False)
    await mw(handler, event, {"event_from_user": SimpleNamespace(id=999)})
    handler.assert_not_awaited()
    event.callback_query.answer.assert_awaited_once()
    # show_alert so the user actually sees it
    assert event.callback_query.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_no_user_is_blocked():
    mw = AccessControlMiddleware({123})
    handler = AsyncMock()
    event = _event()
    await mw(handler, event, {"event_from_user": None})
    handler.assert_not_awaited()
