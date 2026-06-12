import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import engagement, _shared
from bot.states.states import EngagementStates


class FakeUser:
    def __init__(self, user_id=42):
        self.id = user_id


class FakeMessage:
    def __init__(self, text="", user_id=42):
        self.text = text
        self.from_user = FakeUser(user_id)
        self.answer = AsyncMock()
        self.edit_text = AsyncMock()


class FakeCallback:
    def __init__(self, data="", user_id=42):
        self.data = data
        self.from_user = FakeUser(user_id)
        self.message = FakeMessage(user_id=user_id)
        self.answer = AsyncMock()


class FakeFSMContext:
    def __init__(self, data=None):
        self._data = dict(data or {})
        self.state = None

    async def get_data(self):
        return dict(self._data)

    async def update_data(self, **kwargs):
        self._data.update(kwargs)
        return dict(self._data)

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self._data = {}
        self.state = None


POST_URL = "https://www.linkedin.com/posts/x-activity-7448808898326654978-AA"


@pytest.mark.asyncio
async def test_start_sets_waiting_input():
    callback = FakeCallback(data="li:engagement-monitor")
    state = FakeFSMContext()

    await engagement.start_engagement(callback, state)

    assert state.state == EngagementStates.waiting_input
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_url_rejected():
    state = FakeFSMContext()
    message = FakeMessage(text="hello not a url")

    with patch.object(engagement, "fetch_engagers", new=AsyncMock()) as fetch_mock, \
         patch.object(engagement, "run_skill", new=AsyncMock()) as run_mock:
        await engagement.on_input(message, state)

    fetch_mock.assert_not_awaited()
    run_mock.assert_not_awaited()
    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "valid" in sent.lower() and "url" in sent.lower()


@pytest.mark.asyncio
async def test_no_token_tells_user_unavailable():
    state = FakeFSMContext()
    message = FakeMessage(text=POST_URL)

    with patch.object(engagement, "fetch_engagers", new=AsyncMock(return_value=None)) as fetch_mock, \
         patch.object(engagement, "run_skill", new=AsyncMock()) as run_mock:
        await engagement.on_input(message, state)

    fetch_mock.assert_awaited_once()
    run_mock.assert_not_awaited()
    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "apify" in sent.lower() or "unavailable" in sent.lower()


@pytest.mark.asyncio
async def test_engagers_run_skill():
    state = FakeFSMContext()
    message = FakeMessage(text=POST_URL)
    engagers = [{"name": "A"}, {"name": "B"}]

    with patch.object(engagement, "fetch_engagers", new=AsyncMock(return_value=engagers)), \
         patch.object(engagement, "run_skill", new=AsyncMock(return_value="ICP REPORT")) as run_mock:
        await engagement.on_input(message, state)

    run_mock.assert_awaited_once()
    args, kwargs = run_mock.call_args
    assert (args and args[0] == "engagement-monitor") or kwargs.get("skill") == "engagement-monitor"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs.get("engagers") == engagers
    assert user_inputs.get("post_url") == POST_URL

    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "ICP REPORT" in sent

    assert state._data.get("save_skill") == "engagement-monitor"
    assert state._data.get("save_inputs", {}).get("engager_count") == 2


@pytest.mark.asyncio
async def test_no_engagers_tells_user():
    state = FakeFSMContext()
    message = FakeMessage(text=POST_URL)

    with patch.object(engagement, "fetch_engagers", new=AsyncMock(return_value=[])), \
         patch.object(engagement, "run_skill", new=AsyncMock()) as run_mock:
        await engagement.on_input(message, state)

    run_mock.assert_not_awaited()
    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "no engagers" in sent.lower()


@pytest.mark.asyncio
async def test_fetch_engagers_no_token_returns_none(monkeypatch):
    monkeypatch.setattr(_shared.settings, "apify_token", None)
    with patch("bot.services.linkedin.apify_client.ApifyClient") as client_cls:
        result = await _shared.fetch_engagers("url")
    assert result is None
    client_cls.assert_not_called()
