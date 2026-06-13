import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.handlers._fakes import FakeMessage, FakeCallback, FakeFSMContext, fake_session_factory


@pytest.mark.asyncio
async def test_settings_lists_channels():
    from bot.handlers import settings as st
    from bot.db.channels import INSTAGRAM
    message = FakeMessage(text="/settings")
    fake_repo = MagicMock(); fake_repo.get_channels_with_tov = AsyncMock(return_value={INSTAGRAM})
    with patch.object(st, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(st, "async_session_factory", fake_session_factory()):
        await st.cmd_settings(message)
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_settings_delete_removes_and_rerenders():
    from bot.handlers import settings as st
    from bot.db.channels import LINKEDIN
    callback = FakeCallback(data="settings:delete:linkedin")
    fake_repo = MagicMock()
    fake_repo.delete = AsyncMock()
    fake_repo.get_channels_with_tov = AsyncMock(return_value=set())
    with patch.object(st, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(st, "async_session_factory", fake_session_factory()):
        await st.on_settings_delete(callback, FakeFSMContext())
    fake_repo.delete.assert_awaited_once()
    args, kwargs = fake_repo.delete.call_args
    assert LINKEDIN in args or kwargs.get("channel") == LINKEDIN


@pytest.mark.asyncio
async def test_settings_create_enters_method_choice():
    from bot.handlers import settings as st
    from bot.states.states import ToneOfVoiceStates
    callback = FakeCallback(data="settings:create:tiktok")
    state = FakeFSMContext()
    await st.on_settings_create(callback, state)
    assert state.state == ToneOfVoiceStates.choosing_method
    assert (await state.get_data())["channel"] == "tiktok"
    callback.message.edit_text.assert_awaited_once()
    _, kwargs = callback.message.edit_text.call_args
    markup = kwargs["reply_markup"]
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert any(b.callback_data == "tovm:wizard:tiktok" for b in buttons)
    assert any(b.callback_data == "tovm:import:tiktok" for b in buttons)
