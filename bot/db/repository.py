from sqlalchemy import select, update
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

    async def get_active(self, user_id: int) -> ToneOfVoice | None:
        result = await self.session.execute(
            select(ToneOfVoice)
            .where(ToneOfVoice.user_id == user_id, ToneOfVoice.is_active == True)
            .order_by(ToneOfVoice.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def deactivate_all(self, user_id: int) -> None:
        await self.session.execute(
            update(ToneOfVoice)
            .where(ToneOfVoice.user_id == user_id)
            .values(is_active=False)
        )

    async def create(self, user_id: int, name: str, profile_json: dict) -> ToneOfVoice:
        await self.deactivate_all(user_id)
        tov = ToneOfVoice(user_id=user_id, name=name, profile_json=profile_json, is_active=True)
        self.session.add(tov)
        await self.session.flush()
        return tov


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
