import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import planner
from bot.states.states import ContentPlannerStates


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
async def test_start_sets_waiting_role():
    callback = FakeCallback(data="li:content-planner")
    state = FakeFSMContext()

    await planner.start_planner(callback, state)

    assert state.state == ContentPlannerStates.waiting_role
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_role_advances_to_audience():
    state = FakeFSMContext()
    state.state = ContentPlannerStates.waiting_role
    message = FakeMessage(text="founder")

    with patch.object(planner, "run_skill", new=AsyncMock()) as run_mock:
        await planner.on_role(message, state)

    assert state.state == ContentPlannerStates.waiting_audience
    assert state._data.get("planner_role") == "founder"
    message.answer.assert_awaited_once()
    run_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_audience_generates_plan():
    state = FakeFSMContext(data={"planner_role": "founder"})
    state.state = ContentPlannerStates.waiting_audience
    message = FakeMessage(text="VPs of Marketing")

    with patch.object(planner, "run_skill", new=AsyncMock(return_value="7-DAY PLAN")) as run_mock:
        await planner.on_audience(message, state)

    run_mock.assert_awaited_once()
    args, kwargs = run_mock.call_args
    skill = args[0] if args else kwargs.get("skill")
    assert skill == "content-planner"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert user_inputs == {"role": "founder", "audience": "VPs of Marketing"}

    sent = " ".join(str(c.args[0]) for c in message.answer.await_args_list if c.args)
    assert "7-DAY PLAN" in sent

    assert state._data.get("save_skill") == "content-planner"
    assert state._data.get("save_output") == "7-DAY PLAN"
