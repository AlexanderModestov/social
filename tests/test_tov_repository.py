import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.db.models import Base, User
from bot.db.repository import ToneOfVoiceRepository
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(User(telegram_id=1, username="u"))
        await s.flush()
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_then_get_for_channel(session):
    repo = ToneOfVoiceRepository(session)
    await repo.upsert(1, LINKEDIN, "LI", {"v": 1})
    got = await repo.get_for_channel(1, LINKEDIN)
    assert got.profile_json == {"v": 1}
    assert await repo.get_for_channel(1, TIKTOK) is None


@pytest.mark.asyncio
async def test_upsert_overwrites_same_channel(session):
    repo = ToneOfVoiceRepository(session)
    await repo.upsert(1, LINKEDIN, "LI", {"v": 1})
    await repo.upsert(1, LINKEDIN, "LI2", {"v": 2})
    got = await repo.get_for_channel(1, LINKEDIN)
    assert got.profile_json == {"v": 2}
    assert got.name == "LI2"
    assert (await repo.get_channels_with_tov(1)) == {LINKEDIN}


@pytest.mark.asyncio
async def test_get_channels_with_tov_and_delete(session):
    repo = ToneOfVoiceRepository(session)
    await repo.upsert(1, LINKEDIN, "LI", {})
    await repo.upsert(1, INSTAGRAM, "IG", {})
    assert await repo.get_channels_with_tov(1) == {LINKEDIN, INSTAGRAM}
    await repo.delete(1, LINKEDIN)
    assert await repo.get_channels_with_tov(1) == {INSTAGRAM}
