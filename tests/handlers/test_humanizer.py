import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import humanizer
from bot.states.states import HumanizerStates


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
    callback = FakeCallback(data="li:humanizer")
    state = FakeFSMContext()

    await humanizer.start_humanizer(callback, state)

    assert state.state == HumanizerStates.waiting_input
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_paste_runs_humanizer_strict():
    state = FakeFSMContext()
    message = FakeMessage(text="ai slop")

    with patch.object(humanizer, "run_skill", new=AsyncMock(return_value="CLEANED")) as run_mock:
        await humanizer.on_text(message, state)

    run_mock.assert_awaited_once()
    args, kwargs = run_mock.call_args
    assert (args and args[0] == "humanizer") or kwargs.get("skill") == "humanizer"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs == {"draft": "ai slop", "mode": "strict"}

    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "CLEANED" in sent

    assert state.state == HumanizerStates.reviewing
    assert state._data.get("save_skill") == "humanizer"
    assert state._data.get("save_output") == "CLEANED"


@pytest.mark.asyncio
async def test_mode_toggle_reruns_with_mode():
    state = FakeFSMContext({"draft": "x"})
    callback = FakeCallback(data="hmz:forensic")

    with patch.object(humanizer, "run_skill", new=AsyncMock(return_value="FORENSIC OUT")) as run_mock:
        await humanizer.on_mode(callback, state)

    run_mock.assert_awaited_once()
    args, kwargs = run_mock.call_args
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs["mode"] == "forensic"
    assert user_inputs["draft"] == "x"

    callback.message.edit_text.assert_awaited_once()
    sent = " ".join(str(c.args[0]) for c in callback.message.edit_text.await_args_list if c.args)
    assert "FORENSIC OUT" in sent
