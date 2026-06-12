import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import audit
from bot.states.states import PostAuditStates


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
    callback = FakeCallback(data="li:post-audit")
    state = FakeFSMContext()

    await audit.start_audit(callback, state)

    assert state.state == PostAuditStates.waiting_input
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_paste_runs_audit():
    state = FakeFSMContext()
    message = FakeMessage(text="my draft")

    with patch.object(audit, "run_skill", new=AsyncMock(return_value="AUDIT REPORT")) as run_mock:
        await audit.on_text(message, state)

    run_mock.assert_awaited_once()
    args, kwargs = run_mock.call_args
    assert (args and args[0] == "post-audit") or kwargs.get("skill") == "post-audit"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs == {"draft": "my draft", "mode": "audit"}

    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "AUDIT REPORT" in sent

    assert state._data.get("save_skill") == "post-audit"
    assert state._data.get("save_output") == "AUDIT REPORT"
