import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import profile
from bot.states.states import ProfileOptimizerStates


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
    callback = FakeCallback(data="li:profile-optimizer")
    state = FakeFSMContext()

    await profile.start_profile(callback, state)

    assert state.state == ProfileOptimizerStates.waiting_input
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_paste_optimizes_profile():
    state = FakeFSMContext()
    text = "Headline: PM | About: I build things"
    message = FakeMessage(text=text)

    with patch.object(profile, "run_skill", new=AsyncMock(return_value="OPTIMIZED PROFILE")) as run_mock:
        await profile.on_text(message, state)

    run_mock.assert_awaited_once()
    args, kwargs = run_mock.call_args
    assert (args and args[0] == "profile-optimizer") or kwargs.get("skill") == "profile-optimizer"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs == {"profile": text}

    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "OPTIMIZED PROFILE" in sent

    assert state._data.get("save_skill") == "profile-optimizer"
    assert state._data.get("save_output") == "OPTIMIZED PROFILE"


@pytest.mark.asyncio
async def test_blank_reprompts():
    state = FakeFSMContext()
    message = FakeMessage(text="   ")

    with patch.object(profile, "run_skill", new=AsyncMock()) as run_mock:
        await profile.on_text(message, state)

    run_mock.assert_not_awaited()
    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "Paste your profile text" in sent
