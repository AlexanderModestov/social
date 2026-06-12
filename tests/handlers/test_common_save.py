import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import common


class FakeUser:
    def __init__(self, user_id=42):
        self.id = user_id


class FakeMessage:
    def __init__(self, user_id=42):
        self.from_user = FakeUser(user_id)
        self.answer = AsyncMock()
        self.edit_text = AsyncMock()


class FakeCallback:
    def __init__(self, data="skill:save", user_id=42):
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
async def test_skill_save_persists():
    state = FakeFSMContext({
        "save_skill": "humanizer",
        "save_inputs": {"draft": "x"},
        "save_output": "OUT",
    })
    callback = FakeCallback()

    with patch.object(common, "save_history", new=AsyncMock()) as save_mock:
        await common.on_skill_save(callback, state)

    save_mock.assert_awaited_once()
    _, kwargs = save_mock.call_args
    assert kwargs.get("skill") == "humanizer"
    assert kwargs.get("output") == "OUT"

    callback.message.edit_text.assert_awaited_once_with("Saved to your history!")
    assert state.state is None
    assert state._data == {}


@pytest.mark.asyncio
async def test_skill_save_nothing_to_save():
    state = FakeFSMContext()
    callback = FakeCallback()

    with patch.object(common, "save_history", new=AsyncMock()) as save_mock:
        await common.on_skill_save(callback, state)

    save_mock.assert_not_awaited()
    callback.answer.assert_awaited_once()
    _, kwargs = callback.answer.call_args
    assert kwargs.get("show_alert") is True
