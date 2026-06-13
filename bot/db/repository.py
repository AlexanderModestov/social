from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.db.models import User, ToneOfVoice, PostHistory


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, telegram_id: int, username: str | None) -> User:
        user = await self.session.get(User, telegram_id)
        if user is None:
            user = User(telegram_id=telegram_id, username=username)
            self.session.add(user)
            await self.session.flush()
        return user


class ToneOfVoiceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_channel(self, user_id: int, channel: str) -> ToneOfVoice | None:
        result = await self.session.execute(
            select(ToneOfVoice).where(
                ToneOfVoice.user_id == user_id,
                ToneOfVoice.channel == channel,
            )
        )
        return result.scalar_one_or_none()

    async def get_channels_with_tov(self, user_id: int) -> set[str]:
        result = await self.session.execute(
            select(ToneOfVoice.channel).where(ToneOfVoice.user_id == user_id)
        )
        return set(result.scalars().all())

    async def upsert(self, user_id: int, channel: str, name: str, profile_json: dict) -> ToneOfVoice:
        existing = await self.get_for_channel(user_id, channel)
        if existing is not None:
            existing.name = name
            existing.profile_json = profile_json
            await self.session.flush()
            return existing
        tov = ToneOfVoice(
            user_id=user_id, channel=channel, name=name,
            profile_json=profile_json, is_active=True,
        )
        self.session.add(tov)
        await self.session.flush()
        return tov

    async def delete(self, user_id: int, channel: str) -> None:
        existing = await self.get_for_channel(user_id, channel)
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()


class PostHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, platform: str, format: str,
                     input_data: dict, output_data: dict) -> PostHistory:
        post = PostHistory(
            user_id=user_id, platform=platform, format=format,
            input_data=input_data, output_data=output_data
        )
        self.session.add(post)
        await self.session.flush()
        return post
