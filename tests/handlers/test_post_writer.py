import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers.linkedin import post_writer
from bot.states.states import LinkedInStates


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
async def test_start_triggers_on_li_post_writer():
    # The start handler is registered for callback_data "li:post-writer".
    callback = FakeCallback(data="li:post-writer")
    state = FakeFSMContext()

    await post_writer.start_linkedin(callback, state)

    assert state.state == LinkedInStates.collecting_inputs
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_done_routes_through_run_skill():
    state = FakeFSMContext({"links": ["http://x"], "notes": ["a", "b"]})
    message = FakeMessage(text="/done")

    fake_scraper = MagicMock()
    fake_scraper.scrape_urls = AsyncMock(return_value=["ART"])

    with patch.object(post_writer, "ScraperService", return_value=fake_scraper), patch.object(
        post_writer, "run_skill", new=AsyncMock(return_value="DRAFT")
    ) as run_skill_mock:
        await post_writer.on_done(message, state)

    run_skill_mock.assert_awaited_once()
    args, kwargs = run_skill_mock.call_args
    assert (args and args[0] == "post-writer") or kwargs.get("skill") == "post-writer"
    user_inputs = kwargs.get("user_inputs") or args[1]
    assert "a" in user_inputs["notes"] and "b" in user_inputs["notes"]
    assert "ART" in user_inputs["reference_articles"]

    # the generated draft is shown to the user
    sent = " ".join(
        str(c.args[0]) for c in message.answer.await_args_list if c.args
    )
    assert "DRAFT" in sent
    assert state.state == LinkedInStates.editing


@pytest.mark.asyncio
async def test_publish_sends_manual_message():
    state = FakeFSMContext({"generated_post": "MY POST"})
    callback = FakeCallback(data="post:publish")

    publish_mock = MagicMock(return_value={"mode": "manual", "message": "COPY THIS: MY POST"})

    with patch.object(post_writer, "publish", publish_mock):
        await post_writer.on_publish(callback, state)

    publish_mock.assert_called_once_with(
        "post", "MY POST", "https://www.linkedin.com/post/new/"
    )
    callback.message.answer.assert_awaited_once_with("COPY THIS: MY POST")
    callback.answer.assert_awaited_once()
