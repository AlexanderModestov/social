"""Shared test helpers for handler tests (fake aiogram objects + session factory)."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock


class FakeUser:
    def __init__(self, user_id=42, username="tester"):
        self.id = user_id
        self.username = username


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


def fake_session_factory(session=None):
    session = session or AsyncMock()

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory
