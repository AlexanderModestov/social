import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import reply
from bot.states.states import ReplyHandlerStates


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


@pytest.mark.asyncio
async def test_start_sets_waiting_input():
    callback = FakeCallback(data="li:reply-handler")
    state = FakeFSMContext()

    await reply.start_reply(callback, state)

    assert state.state == ReplyHandlerStates.waiting_input
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_paste_drafts_reply():
    state = FakeFSMContext()
    message = FakeMessage(text="I disagree because...")

    with patch.object(reply, "run_skill", new=AsyncMock(return_value="MY REPLY")) as run_mock:
        await reply.on_input(message, state)

    run_mock.assert_awaited_once()
    args, kwargs = run_mock.call_args
    assert (args and args[0] == "reply-handler") or kwargs.get("skill") == "reply-handler"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs == {"thread": "I disagree because..."}

    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "MY REPLY" in sent

    assert state._data.get("save_skill") == "reply-handler"
    assert state._data.get("save_output") == "MY REPLY"


@pytest.mark.asyncio
async def test_url_without_apify_asks_paste():
    state = FakeFSMContext()
    message = FakeMessage(text="https://www.linkedin.com/posts/someone_activity-123")

    with patch.object(reply, "resolve_source", new=AsyncMock(return_value=("", "needs_paste"))), \
         patch.object(reply, "run_skill", new=AsyncMock()) as run_mock:
        await reply.on_input(message, state)

    run_mock.assert_not_awaited()
    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "paste" in sent.lower()
