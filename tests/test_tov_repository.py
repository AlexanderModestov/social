import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.db.models import Base, ToneOfVoice, User
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


@pytest.mark.asyncio
async def test_unique_constraint_rejects_duplicate(session):
    session.add(
        ToneOfVoice(
            user_id=1, channel=LINKEDIN, name="LI", profile_json={"v": 1}, is_active=True
        )
    )
    await session.flush()
    session.add(
        ToneOfVoice(
            user_id=1, channel=LINKEDIN, name="LI-dup", profile_json={"v": 2}, is_active=True
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_per_user_isolation(session):
    session.add(User(telegram_id=2, username="u2"))
    await session.flush()

    repo = ToneOfVoiceRepository(session)
    await repo.upsert(1, LINKEDIN, "LI-1", {"owner": 1})
    await repo.upsert(2, LINKEDIN, "LI-2", {"owner": 2})

    got1 = await repo.get_for_channel(1, LINKEDIN)
    got2 = await repo.get_for_channel(2, LINKEDIN)
    assert got1.profile_json == {"owner": 1}
    assert got2.profile_json == {"owner": 2}
    assert got1.id != got2.id

    assert await repo.get_channels_with_tov(1) == {LINKEDIN}
    assert await repo.get_channels_with_tov(2) == {LINKEDIN}
