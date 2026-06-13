from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tone_of_voices: Mapped[list["ToneOfVoice"]] = relationship(back_populates="user")
    post_history: Mapped[list["PostHistory"]] = relationship(back_populates="user")


class ToneOfVoice(Base):
    __tablename__ = "tone_of_voices"
    __table_args__ = (UniqueConstraint("user_id", "channel", name="uq_tov_user_channel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    profile_json: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="tone_of_voices")


class PostHistory(Base):
    __tablename__ = "post_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    platform: Mapped[str] = mapped_column(String(32))
    format: Mapped[str] = mapped_column(String(32))
    input_data: Mapped[dict] = mapped_column(JSON)
    output_data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="post_history")
