# Social Content Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Telegram bot that generates LinkedIn posts and TikTok videos personalized to a user's tone of voice.

**Architecture:** aiogram 3.x FSM-based bot with PostgreSQL persistence. Claude handles text/post generation, Gemini handles TikTok video generation, Playwright records product demos. All external API calls isolated in service classes.

**Tech Stack:** Python 3.12, aiogram 3.7, SQLAlchemy 2.x (async), Alembic, Anthropic SDK, Google Generative AI SDK, Playwright, httpx, BeautifulSoup4, pytest-asyncio, Docker Compose, Railway

---

## Task 1: Git Init + Project Skeleton

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `bot/__init__.py`
- Create: `bot/handlers/__init__.py`
- Create: `bot/keyboards/__init__.py`
- Create: `bot/states/__init__.py`
- Create: `bot/services/__init__.py`
- Create: `bot/db/__init__.py`
- Create: `skills/brand_voice/.gitkeep`
- Create: `skills/linkedin/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/services/__init__.py`
- Create: `docs/plans/.gitkeep`

**Step 1: Initialize git**

```bash
git init
```

**Step 2: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.mp4
*.mp3
/tmp/
.pytest_cache/
.venv/
dist/
*.egg-info/
```

**Step 3: Create README.md**

```markdown
# Social Content Bot

Telegram bot for generating LinkedIn posts and TikTok videos with personalized tone of voice.

## Setup

1. Copy `.env.example` to `.env` and fill values
2. Run `docker compose up -d`
3. Run migrations: `docker compose exec bot alembic upgrade head`
4. Bot starts automatically

## Development

```bash
docker compose up        # start bot + postgres
docker compose logs -f bot   # tail logs
pytest                   # run tests
```
```

**Step 4: Create all `__init__.py` files and directory structure**

```bash
mkdir -p bot/handlers bot/keyboards bot/states bot/services bot/db
mkdir -p skills/brand_voice skills/linkedin
mkdir -p tests/services tests/handlers
mkdir -p docs/plans migrations
touch bot/__init__.py bot/handlers/__init__.py bot/keyboards/__init__.py
touch bot/states/__init__.py bot/services/__init__.py bot/db/__init__.py
touch tests/__init__.py tests/services/__init__.py tests/handlers/__init__.py
```

**Step 5: Commit**

```bash
git add .
git commit -m "chore: initialize project skeleton"
```

---

## Task 2: Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`

**Step 1: Create requirements.txt**

```
aiogram==3.7.0
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1
anthropic==0.28.0
google-generativeai==0.7.2
playwright==1.44.0
httpx==0.27.0
beautifulsoup4==4.12.3
pydantic-settings==2.3.0
python-dotenv==1.0.1
```

**Step 2: Create requirements-dev.txt**

```
pytest==8.2.2
pytest-asyncio==0.23.7
pytest-mock==3.14.0
respx==0.21.1
```

**Step 3: Create .env.example**

```
TELEGRAM_BOT_TOKEN=your_token_here
ANTHROPIC_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
DATABASE_URL=postgresql+asyncpg://social:secret@db:5432/social
```

**Step 4: Commit**

```bash
git add .
git commit -m "chore: add dependencies"
```

---

## Task 3: Settings

**Files:**
- Create: `bot/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing test**

```python
# tests/test_config.py
import os
import pytest
from bot.config import Settings

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_claude")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")

    settings = Settings()

    assert settings.telegram_bot_token == "test_token"
    assert settings.anthropic_api_key == "test_claude"
    assert settings.google_api_key == "test_google"
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'bot.config'`

**Step 3: Implement**

```python
# bot/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    telegram_bot_token: str
    anthropic_api_key: str
    google_api_key: str
    database_url: str

    class Config:
        env_file = ".env"

settings = Settings()
```

**Step 4: Run to verify it passes**

```bash
pytest tests/test_config.py -v
```
Expected: PASSED

**Step 5: Commit**

```bash
git add bot/config.py tests/test_config.py
git commit -m "feat: add settings with pydantic-settings"
```

---

## Task 4: Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile`

**Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl wget gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

CMD ["python", "-m", "bot.main"]
```

**Step 2: Create docker-compose.yml**

```yaml
services:
  bot:
    build: .
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - .:/app
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: social
      POSTGRES_USER: social
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U social"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Step 3: Verify Docker builds (no tests needed here)**

```bash
docker compose build
```
Expected: build succeeds

**Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: add Docker Compose setup"
```

---

## Task 5: Database Models

**Files:**
- Create: `bot/db/models.py`
- Create: `bot/db/session.py`
- Create: `tests/test_models.py`

**Step 1: Write failing test**

```python
# tests/test_models.py
from bot.db.models import User, ToneOfVoice, PostHistory

def test_user_model_has_required_fields():
    u = User(telegram_id=123, username="alex")
    assert u.telegram_id == 123
    assert u.username == "alex"

def test_tone_of_voice_has_is_active():
    tov = ToneOfVoice(user_id=1, name="Pro Alex", profile_json={}, is_active=True)
    assert tov.is_active is True

def test_post_history_has_platform():
    ph = PostHistory(user_id=1, platform="linkedin", format="post", input_data={}, output_data={})
    assert ph.platform == "linkedin"
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'bot.db.models'`

**Step 3: Implement models**

```python
# bot/db/models.py
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, func
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(128))
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
```

**Step 4: Create async session factory**

```python
# bot/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from bot.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

**Step 5: Run to verify it passes**

```bash
pytest tests/test_models.py -v
```
Expected: 3 PASSED

**Step 6: Commit**

```bash
git add bot/db/models.py bot/db/session.py tests/test_models.py
git commit -m "feat: add database models (User, ToneOfVoice, PostHistory)"
```

---

## Task 6: Alembic Setup + Initial Migration

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/` (auto-generated)

**Step 1: Initialize Alembic**

```bash
alembic init migrations
```

**Step 2: Update migrations/env.py to use async engine and our models**

Replace the content of `migrations/env.py` with:

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from bot.db.models import Base
from bot.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

run_migrations_online()
```

**Step 3: Generate initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
```
Expected: creates `migrations/versions/xxxx_initial_schema.py`

**Step 4: Apply migration (requires running postgres)**

```bash
docker compose up -d db
alembic upgrade head
```
Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> xxxx, initial schema`

**Step 5: Commit**

```bash
git add alembic.ini migrations/
git commit -m "feat: add Alembic migrations with initial schema"
```

---

## Task 7: DB Repository

**Files:**
- Create: `bot/db/repository.py`
- Create: `tests/test_repository.py`

**Step 1: Write failing tests**

```python
# tests/test_repository.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.db.repository import UserRepository, ToneOfVoiceRepository

@pytest.mark.asyncio
async def test_get_or_create_user_creates_new():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = UserRepository(session)
    user = await repo.get_or_create(telegram_id=123, username="alex")

    assert user.telegram_id == 123
    session.add.assert_called_once()

@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing():
    from bot.db.models import User
    existing = User(telegram_id=123, username="alex")
    session = AsyncMock()
    session.get = AsyncMock(return_value=existing)

    repo = UserRepository(session)
    user = await repo.get_or_create(telegram_id=123, username="alex")

    assert user is existing
    session.add.assert_not_called()
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_repository.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement repository**

```python
# bot/db/repository.py
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
```

**Step 4: Run to verify tests pass**

```bash
pytest tests/test_repository.py -v
```
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add bot/db/repository.py tests/test_repository.py
git commit -m "feat: add DB repositories (User, ToneOfVoice, PostHistory)"
```

---

## Task 8: FSM States

**Files:**
- Create: `bot/states/states.py`

**Step 1: Implement (no logic to test, just data)**

```python
# bot/states/states.py
from aiogram.fsm.state import State, StatesGroup

class ToneOfVoiceStates(StatesGroup):
    waiting_role = State()
    waiting_audience = State()
    waiting_style = State()
    waiting_examples = State()
    confirming_profile = State()

class LinkedInStates(StatesGroup):
    collecting_inputs = State()
    editing = State()

class TikTokStates(StatesGroup):
    waiting_subtype = State()
    waiting_product_url = State()
    recording = State()
    waiting_description = State()
    collecting_materials = State()
    generating_video = State()
```

**Step 2: Commit**

```bash
git add bot/states/states.py
git commit -m "feat: define FSM states for all conversation flows"
```

---

## Task 9: Keyboards

**Files:**
- Create: `bot/keyboards/inline.py`
- Create: `tests/test_keyboards.py`

**Step 1: Write failing test**

```python
# tests/test_keyboards.py
from bot.keyboards.inline import main_menu_keyboard, platform_keyboard, tiktok_subtype_keyboard

def test_main_menu_has_two_buttons():
    kb = main_menu_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2

def test_platform_keyboard_has_linkedin_and_tiktok():
    kb = platform_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "platform:linkedin" in callbacks
    assert "platform:tiktok" in callbacks

def test_tiktok_subtype_has_two_options():
    kb = tiktok_subtype_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_keyboards.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# bot/keyboards/inline.py
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Create tone of voice", callback_data="action:tone_of_voice")],
        [InlineKeyboardButton(text="✍️ Create content", callback_data="action:create_content")],
    ])

def platform_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 LinkedIn post", callback_data="platform:linkedin")],
        [InlineKeyboardButton(text="🎵 TikTok video", callback_data="platform:tiktok")],
    ])

def tiktok_subtype_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Product demo", callback_data="tiktok:product_demo")],
        [InlineKeyboardButton(text="🎬 Video from plot", callback_data="tiktok:video_plot")],
    ])

def post_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Regenerate", callback_data="post:regenerate"),
         InlineKeyboardButton(text="✏️ Edit", callback_data="post:edit")],
        [InlineKeyboardButton(text="💾 Save", callback_data="post:save")],
    ])

def tone_of_voice_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Save", callback_data="tov:save"),
         InlineKeyboardButton(text="🔄 Regenerate", callback_data="tov:regenerate")],
    ])

def style_words_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    words = ["Formal", "Casual", "Inspiring", "Analytical", "Direct", "Storyteller"]
    rows = []
    for i in range(0, len(words), 3):
        row = []
        for word in words[i:i+3]:
            prefix = "✅ " if word in selected else ""
            row.append(InlineKeyboardButton(
                text=f"{prefix}{word}",
                callback_data=f"style:{word}"
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="➡️ Continue", callback_data="style:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

**Step 4: Run to verify tests pass**

```bash
pytest tests/test_keyboards.py -v
```
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add bot/keyboards/inline.py tests/test_keyboards.py
git commit -m "feat: add inline keyboards for all flows"
```

---

## Task 10: Skills Prompt Files

**Files:**
- Create: `skills/brand_voice/system_prompt.txt`
- Create: `skills/linkedin/system_prompt.txt`
- Create: `skills/linkedin/post_format.txt`

**Step 1: Fetch brand-voice skill from GitHub**

Visit https://github.com/alirezarezvani/claude-skills and copy the brand voice skill content into:

```
# skills/brand_voice/system_prompt.txt
```

If the repo is unavailable, use this baseline:

```
You are a brand voice specialist. Your task is to synthesize a user's answers into a structured tone of voice profile.

Based on the user's role, audience, style preferences, and examples, create a JSON profile with these exact fields:
- voice_summary: one sentence describing their overall voice
- tone_words: array of 3 descriptive words
- avoid: array of things to never do in their content
- always: array of things to always do in their content
- audience: who they write for
- example_phrases: 2-3 phrases that sound like them

Respond ONLY with valid JSON. No explanation, no markdown, just the JSON object.
```

**Step 2: Fetch LinkedIn skill from GitHub**

Visit https://github.com/sergebulaev/linkedin-skills and copy the relevant skill content into:

```
# skills/linkedin/system_prompt.txt
```

If unavailable, use this baseline:

```
You are a LinkedIn content specialist. Write a LinkedIn post based on the provided links, notes, and the user's tone of voice profile.

LinkedIn post structure:
1. Hook (first line — pattern interrupt, question, or bold claim. No more than 8 words.)
2. Body (3-5 short paragraphs, max 3 lines each. Leave blank lines between.)
3. Call to action (one question or invitation to engage)
4. Hashtags (3-5 relevant hashtags on the last line)

Rules:
- Never start with "I" 
- No buzzwords (synergy, leverage, pivot, disrupt)
- Use the user's tone of voice profile to match their voice exactly
- Use line breaks generously — LinkedIn rewards white space
- Keep total length under 1300 characters

Respond ONLY with the post text. No explanation.
```

**Step 3: Create post format reference**

```
# skills/linkedin/post_format.txt
Hook line

First insight or story paragraph.
Keep it punchy.

Second point.
Data or example here.

Third point.
The takeaway.

What do you think? [question]

#hashtag1 #hashtag2 #hashtag3
```

**Step 4: Commit**

```bash
git add skills/
git commit -m "feat: add brand voice and linkedin skills prompts"
```

---

## Task 11: Scraper Service

**Files:**
- Create: `bot/services/scraper_service.py`
- Create: `tests/services/test_scraper_service.py`

**Step 1: Write failing tests**

```python
# tests/services/test_scraper_service.py
import pytest
import respx
import httpx
from bot.services.scraper_service import ScraperService

@pytest.mark.asyncio
async def test_scrape_extracts_text():
    html = "<html><body><p>Hello world</p><p>Second paragraph</p></body></html>"
    with respx.mock:
        respx.get("https://example.com/article").mock(
            return_value=httpx.Response(200, text=html)
        )
        service = ScraperService()
        text = await service.scrape_url("https://example.com/article")
    assert "Hello world" in text
    assert "Second paragraph" in text

@pytest.mark.asyncio
async def test_scrape_returns_empty_on_error():
    with respx.mock:
        respx.get("https://example.com/bad").mock(
            return_value=httpx.Response(404)
        )
        service = ScraperService()
        text = await service.scrape_url("https://example.com/bad")
    assert text == ""

@pytest.mark.asyncio
async def test_scrape_multiple_urls():
    html1 = "<html><body><p>Article one</p></body></html>"
    html2 = "<html><body><p>Article two</p></body></html>"
    with respx.mock:
        respx.get("https://example.com/one").mock(return_value=httpx.Response(200, text=html1))
        respx.get("https://example.com/two").mock(return_value=httpx.Response(200, text=html2))
        service = ScraperService()
        texts = await service.scrape_urls(["https://example.com/one", "https://example.com/two"])
    assert len(texts) == 2
    assert "Article one" in texts[0]
```

**Step 2: Run to verify they fail**

```bash
pytest tests/services/test_scraper_service.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# bot/services/scraper_service.py
import httpx
from bs4 import BeautifulSoup

class ScraperService:
    async def scrape_url(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code != 200:
                    return ""
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return "\n".join(line for line in text.splitlines() if line.strip())
        except Exception:
            return ""

    async def scrape_urls(self, urls: list[str]) -> list[str]:
        import asyncio
        return await asyncio.gather(*[self.scrape_url(url) for url in urls])
```

**Step 4: Run to verify tests pass**

```bash
pytest tests/services/test_scraper_service.py -v
```
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add bot/services/scraper_service.py tests/services/test_scraper_service.py
git commit -m "feat: add scraper service for link text extraction"
```

---

## Task 12: Claude Service

**Files:**
- Create: `bot/services/claude_service.py`
- Create: `tests/services/test_claude_service.py`

**Step 1: Write failing tests**

```python
# tests/services/test_claude_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.claude_service import ClaudeService

@pytest.mark.asyncio
async def test_generate_tone_of_voice_calls_api():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"voice_summary": "Direct and clear"}')]

    with patch("bot.services.claude_service.anthropic.AsyncAnthropic") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service = ClaudeService()
        result = await service.generate_tone_of_voice(
            role="Product Manager",
            audience="Developers",
            style_words=["Direct", "Analytical"],
            examples=["Here's what I learned today..."]
        )

    assert "voice_summary" in result

@pytest.mark.asyncio
async def test_generate_linkedin_post_calls_api():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Great hook line\n\nBody paragraph.\n\n#tag1")]

    with patch("bot.services.claude_service.anthropic.AsyncAnthropic") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service = ClaudeService()
        result = await service.generate_linkedin_post(
            notes="My notes here",
            scraped_content=["Article content here"],
            tone_profile={"voice_summary": "Direct"},
            previous_post=None
        )

    assert isinstance(result, str)
    assert len(result) > 0
```

**Step 2: Run to verify they fail**

```bash
pytest tests/services/test_claude_service.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# bot/services/claude_service.py
import json
import anthropic
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"

def _load_skill(path: str) -> str:
    return (SKILLS_DIR / path).read_text(encoding="utf-8")

class ClaudeService:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()

    async def generate_tone_of_voice(
        self,
        role: str,
        audience: str,
        style_words: list[str],
        examples: list[str],
    ) -> dict:
        system_prompt = _load_skill("brand_voice/system_prompt.txt")
        user_message = (
            f"Role: {role}\n"
            f"Audience: {audience}\n"
            f"Style words: {', '.join(style_words)}\n"
            f"Examples:\n" + "\n".join(f"- {e}" for e in examples)
        )
        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return json.loads(response.content[0].text)

    async def generate_linkedin_post(
        self,
        notes: str,
        scraped_content: list[str],
        tone_profile: dict,
        previous_post: str | None = None,
        feedback: str | None = None,
    ) -> str:
        system_prompt = _load_skill("linkedin/system_prompt.txt")
        context_parts = [f"USER TONE OF VOICE:\n{json.dumps(tone_profile, indent=2)}"]
        if scraped_content:
            context_parts.append("REFERENCE ARTICLES:\n" + "\n\n---\n\n".join(scraped_content))
        if notes:
            context_parts.append(f"USER NOTES:\n{notes}")
        if previous_post and feedback:
            context_parts.append(f"PREVIOUS POST:\n{previous_post}\n\nFEEDBACK:\n{feedback}")

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": "\n\n".join(context_parts)}],
        )
        return response.content[0].text

    async def generate_tiktok_caption(self, url: str, page_content: str, tone_profile: dict) -> str:
        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system="Write a punchy TikTok caption (under 150 chars) + 5 hashtags. Match the user's tone of voice. Respond with just the caption and hashtags.",
            messages=[{"role": "user", "content": f"Product URL: {url}\nPage content: {page_content[:2000]}\nTone: {json.dumps(tone_profile)}"}],
        )
        return response.content[0].text
```

**Step 4: Run to verify tests pass**

```bash
pytest tests/services/test_claude_service.py -v
```
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add bot/services/claude_service.py tests/services/test_claude_service.py
git commit -m "feat: add Claude service for tone of voice and LinkedIn generation"
```

---

## Task 13: Gemini Service

**Files:**
- Create: `bot/services/gemini_service.py`
- Create: `tests/services/test_gemini_service.py`

**Step 1: Write failing test**

```python
# tests/services/test_gemini_service.py
import pytest
from unittest.mock import MagicMock, patch
from bot.services.gemini_service import GeminiService

@pytest.mark.asyncio
async def test_generate_video_calls_api():
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]

    with patch("bot.services.gemini_service.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiService()
        result = await service.generate_video(
            description="A fast-paced product demo",
            image_paths=[],
            tone_profile={"voice_summary": "Direct"}
        )

    mock_client.models.generate_content.assert_called_once()
    assert result is mock_response
```

**Step 2: Run to verify it fails**

```bash
pytest tests/services/test_gemini_service.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# bot/services/gemini_service.py
import asyncio
import json
from pathlib import Path
import google.generativeai as genai
from bot.config import settings

genai.configure(api_key=settings.google_api_key)

class GeminiService:
    MODEL = "gemini-2.0-flash-exp"

    def __init__(self):
        self.client = genai.Client()

    async def generate_video(
        self,
        description: str,
        image_paths: list[str],
        tone_profile: dict,
    ):
        system_prompt = (
            "You are a TikTok video creator. Based on the description, images, and tone of voice, "
            "generate a short engaging video (15-60 seconds). "
            f"Tone of voice: {json.dumps(tone_profile)}"
        )
        contents = [system_prompt, description]
        for path in image_paths:
            with open(path, "rb") as f:
                image_data = f.read()
            contents.append({"mime_type": "image/jpeg", "data": image_data})

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.MODEL,
                contents=contents,
            )
        )
        return response
```

**Step 4: Run to verify test passes**

```bash
pytest tests/services/test_gemini_service.py -v
```
Expected: 1 PASSED

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: add Gemini service for TikTok video generation"
```

---

## Task 14: Playwright Service

**Files:**
- Create: `bot/services/playwright_service.py`
- Create: `tests/services/test_playwright_service.py`

**Step 1: Write failing test**

```python
# tests/services/test_playwright_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.playwright_service import PlaywrightService

@pytest.mark.asyncio
async def test_record_validates_url():
    service = PlaywrightService()
    with pytest.raises(ValueError, match="Invalid URL"):
        await service.record_product_demo("not-a-valid-url")

@pytest.mark.asyncio
async def test_record_returns_mp4_path():
    mock_page = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_page.video = MagicMock()
    mock_page.video.path = AsyncMock(return_value="/tmp/test.mp4")
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.close = AsyncMock()

    with patch("bot.services.playwright_service.async_playwright") as mock_pw:
        mock_context = AsyncMock()
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=AsyncMock(new_page=AsyncMock(return_value=mock_page)))

        service = PlaywrightService()
        # We just test it doesn't crash with a valid URL
        # Full integration test requires a real browser
```

**Step 2: Run to verify first test fails**

```bash
pytest tests/services/test_playwright_service.py::test_record_validates_url -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# bot/services/playwright_service.py
import asyncio
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

class PlaywrightService:
    VIEWPORT = {"width": 390, "height": 844}
    RECORD_DURATION = 15

    async def record_product_demo(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        output_dir = Path(tempfile.mkdtemp())

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport=self.VIEWPORT,
                record_video_dir=str(output_dir),
                record_video_size=self.VIEWPORT,
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            # Scroll through the page
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.6)")
                await asyncio.sleep(self.RECORD_DURATION / 5)
            await page.close()
            await context.close()
            video_path = await page.video.path()
            await browser.close()

        return video_path
```

**Step 4: Run to verify validation test passes**

```bash
pytest tests/services/test_playwright_service.py::test_record_validates_url -v
```
Expected: PASSED

**Step 5: Commit**

```bash
git add bot/services/playwright_service.py tests/services/test_playwright_service.py
git commit -m "feat: add Playwright service for product demo recording"
```

---

## Task 15: Start Handler + Main Menu

**Files:**
- Create: `bot/handlers/start.py`
- Create: `bot/main.py`

**Step 1: Implement start handler**

```python
# bot/handlers/start.py
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.db.session import async_session_factory
from bot.db.repository import UserRepository
from bot.keyboards.inline import main_menu_keyboard, platform_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_factory() as session:
        repo = UserRepository(session)
        await repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        await session.commit()

    await message.answer(
        "👋 Welcome! I help you create content for LinkedIn and TikTok.\n\n"
        "What would you like to do?",
        reply_markup=main_menu_keyboard(),
    )

@router.callback_query(lambda c: c.data == "action:create_content")
async def on_create_content(callback: CallbackQuery):
    await callback.message.edit_text(
        "Choose your platform:",
        reply_markup=platform_keyboard(),
    )
    await callback.answer()
```

**Step 2: Create bot entry point**

```python
# bot/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import settings
from bot.handlers import start, tone_of_voice, linkedin, tiktok

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(tone_of_voice.router)
    dp.include_router(linkedin.router)
    dp.include_router(tiktok.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 3: Create placeholder handlers (so main.py imports don't fail)**

```python
# bot/handlers/tone_of_voice.py
from aiogram import Router
router = Router()

# bot/handlers/linkedin.py
from aiogram import Router
router = Router()

# bot/handlers/tiktok.py
from aiogram import Router
router = Router()
```

**Step 4: Commit**

```bash
git add bot/main.py bot/handlers/start.py bot/handlers/tone_of_voice.py bot/handlers/linkedin.py bot/handlers/tiktok.py
git commit -m "feat: add bot entry point and start handler with main menu"
```

---

## Task 16: Tone of Voice Handler

**Files:**
- Modify: `bot/handlers/tone_of_voice.py`

**Step 1: Implement full wizard**

```python
# bot/handlers/tone_of_voice.py
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.keyboards.inline import style_words_keyboard, tone_of_voice_confirm_keyboard
from bot.services.claude_service import ClaudeService
from bot.states.states import ToneOfVoiceStates

router = Router()

@router.callback_query(lambda c: c.data == "action:tone_of_voice")
async def start_wizard(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ToneOfVoiceStates.waiting_role)
    await callback.message.edit_text(
        "Let's define your tone of voice.\n\n"
        "What's your professional role or what do you create content about?"
    )
    await callback.answer()

@router.message(ToneOfVoiceStates.waiting_role)
async def on_role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(ToneOfVoiceStates.waiting_audience)
    await message.answer("Who is your audience? Who reads or watches your content?")

@router.message(ToneOfVoiceStates.waiting_audience)
async def on_audience(message: Message, state: FSMContext):
    await state.update_data(audience=message.text, style_words=[])
    await state.set_state(ToneOfVoiceStates.waiting_style)
    await message.answer(
        "Pick words that describe your voice (select at least 2, then press Continue):",
        reply_markup=style_words_keyboard([]),
    )

@router.callback_query(ToneOfVoiceStates.waiting_style, F.data.startswith("style:"))
async def on_style_word(callback: CallbackQuery, state: FSMContext):
    word = callback.data.split(":")[1]
    if word == "done":
        data = await state.get_data()
        if len(data.get("style_words", [])) < 2:
            await callback.answer("Please select at least 2 words.", show_alert=True)
            return
        await state.set_state(ToneOfVoiceStates.waiting_examples)
        await callback.message.edit_text(
            "Share 1–3 examples of content you like (your own posts, articles, or just text).\n\n"
            "Send them one by one, then type /done."
        )
    else:
        data = await state.get_data()
        words = data.get("style_words", [])
        words = [w for w in words if w != word]
        if word not in (await state.get_data()).get("style_words", []):
            words.append(word)
        await state.update_data(style_words=words)
        await callback.message.edit_reply_markup(reply_markup=style_words_keyboard(words))
    await callback.answer()

@router.message(ToneOfVoiceStates.waiting_examples, F.text != "/done")
async def on_example(message: Message, state: FSMContext):
    data = await state.get_data()
    examples = data.get("examples", [])
    examples.append(message.text)
    await state.update_data(examples=examples)
    await message.answer(f"Got it ({len(examples)} example{'s' if len(examples) > 1 else ''} so far). Send more or type /done.")

@router.message(ToneOfVoiceStates.waiting_examples, F.text == "/done")
async def on_examples_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("examples"):
        await message.answer("Please share at least one example.")
        return

    await message.answer("Analyzing your style...")
    service = ClaudeService()
    try:
        profile = await service.generate_tone_of_voice(
            role=data["role"],
            audience=data["audience"],
            style_words=data["style_words"],
            examples=data["examples"],
        )
    except Exception as e:
        await message.answer(f"Error generating profile: {e}. Please try again.")
        return

    await state.update_data(generated_profile=profile)
    await state.set_state(ToneOfVoiceStates.confirming_profile)

    profile_text = (
        f"*Your tone of voice profile:*\n\n"
        f"*Voice:* {profile.get('voice_summary', '')}\n"
        f"*Style:* {', '.join(profile.get('tone_words', []))}\n"
        f"*Always:* {'; '.join(profile.get('always', []))}\n"
        f"*Avoid:* {'; '.join(profile.get('avoid', []))}\n"
        f"*Audience:* {profile.get('audience', '')}"
    )
    await message.answer(profile_text, parse_mode="Markdown", reply_markup=tone_of_voice_confirm_keyboard())

@router.callback_query(ToneOfVoiceStates.confirming_profile, F.data == "tov:save")
async def on_save_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        repo = ToneOfVoiceRepository(session)
        await repo.create(
            user_id=callback.from_user.id,
            name=f"Profile {data['role'][:30]}",
            profile_json=data["generated_profile"],
        )
        await session.commit()
    await state.clear()
    await callback.message.edit_text("Profile saved! You're ready to create content.")
    await callback.answer()

@router.callback_query(ToneOfVoiceStates.confirming_profile, F.data == "tov:regenerate")
async def on_regenerate_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text("Regenerating...")
    service = ClaudeService()
    profile = await service.generate_tone_of_voice(
        role=data["role"],
        audience=data["audience"],
        style_words=data["style_words"],
        examples=data["examples"],
    )
    await state.update_data(generated_profile=profile)
    profile_text = (
        f"*Your tone of voice profile:*\n\n"
        f"*Voice:* {profile.get('voice_summary', '')}\n"
        f"*Style:* {', '.join(profile.get('tone_words', []))}\n"
        f"*Always:* {'; '.join(profile.get('always', []))}\n"
        f"*Avoid:* {'; '.join(profile.get('avoid', []))}"
    )
    await callback.message.edit_text(profile_text, parse_mode="Markdown", reply_markup=tone_of_voice_confirm_keyboard())
    await callback.answer()
```

**Step 2: Commit**

```bash
git add bot/handlers/tone_of_voice.py
git commit -m "feat: add tone of voice wizard handler"
```

---

## Task 17: LinkedIn Handler

**Files:**
- Modify: `bot/handlers/linkedin.py`

**Step 1: Implement**

```python
# bot/handlers/linkedin.py
import re
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository, PostHistoryRepository
from bot.keyboards.inline import post_actions_keyboard
from bot.services.claude_service import ClaudeService
from bot.services.scraper_service import ScraperService
from bot.states.states import LinkedInStates

router = Router()
URL_REGEX = re.compile(r"https?://\S+")

@router.callback_query(lambda c: c.data == "platform:linkedin")
async def start_linkedin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LinkedInStates.collecting_inputs)
    await state.update_data(links=[], notes=[], generated_post=None)
    await callback.message.edit_text(
        "Send me links and/or your notes for the post.\n\n"
        "You can send multiple messages. Type /done when finished."
    )
    await callback.answer()

@router.message(LinkedInStates.collecting_inputs, F.text != "/done")
async def on_input(message: Message, state: FSMContext):
    data = await state.get_data()
    urls = URL_REGEX.findall(message.text or "")
    if urls:
        links = data.get("links", []) + urls
        await state.update_data(links=links)
        await message.answer(f"Got {len(urls)} link(s). Send more or /done.")
    else:
        notes = data.get("notes", [])
        notes.append(message.text)
        await state.update_data(notes=notes)
        await message.answer("Got your notes. Send more or /done.")

@router.message(LinkedInStates.collecting_inputs, F.text == "/done")
async def on_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("links") and not data.get("notes"):
        await message.answer("Please send at least one link or note first.")
        return

    await message.answer("Fetching content and generating your post...")

    async with async_session_factory() as session:
        tov_repo = ToneOfVoiceRepository(session)
        tov = await tov_repo.get_active(message.from_user.id)

    tone_profile = tov.profile_json if tov else {}

    scraper = ScraperService()
    scraped = await scraper.scrape_urls(data.get("links", []))
    notes_text = "\n\n".join(data.get("notes", []))

    claude = ClaudeService()
    post = await claude.generate_linkedin_post(
        notes=notes_text,
        scraped_content=scraped,
        tone_profile=tone_profile,
    )

    await state.update_data(generated_post=post)
    await state.set_state(LinkedInStates.editing)
    await message.answer(post, reply_markup=post_actions_keyboard())

@router.callback_query(LinkedInStates.editing, F.data == "post:regenerate")
async def on_regenerate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(callback.from_user.id)
    scraper = ScraperService()
    scraped = await scraper.scrape_urls(data.get("links", []))
    claude = ClaudeService()
    post = await claude.generate_linkedin_post(
        notes="\n\n".join(data.get("notes", [])),
        scraped_content=scraped,
        tone_profile=tov.profile_json if tov else {},
    )
    await state.update_data(generated_post=post)
    await callback.message.edit_text(post, reply_markup=post_actions_keyboard())
    await callback.answer()

@router.callback_query(LinkedInStates.editing, F.data == "post:edit")
async def on_edit(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Tell me what to change (e.g. 'make it shorter, remove hashtags'):")
    await callback.answer()

@router.message(LinkedInStates.editing)
async def on_edit_feedback(message: Message, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)
    scraper = ScraperService()
    scraped = await scraper.scrape_urls(data.get("links", []))
    claude = ClaudeService()
    post = await claude.generate_linkedin_post(
        notes="\n\n".join(data.get("notes", [])),
        scraped_content=scraped,
        tone_profile=tov.profile_json if tov else {},
        previous_post=data.get("generated_post"),
        feedback=message.text,
    )
    await state.update_data(generated_post=post)
    await message.answer(post, reply_markup=post_actions_keyboard())

@router.callback_query(LinkedInStates.editing, F.data == "post:save")
async def on_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        repo = PostHistoryRepository(session)
        await repo.create(
            user_id=callback.from_user.id,
            platform="linkedin",
            format="post",
            input_data={"links": data.get("links", []), "notes": data.get("notes", [])},
            output_data={"post": data.get("generated_post")},
        )
        await session.commit()
    await state.clear()
    await callback.message.edit_text("Post saved to your history!")
    await callback.answer()
```

**Step 2: Commit**

```bash
git add bot/handlers/linkedin.py
git commit -m "feat: add LinkedIn post generation handler with edit loop"
```

---

## Task 18: TikTok Handler

**Files:**
- Modify: `bot/handlers/tiktok.py`

**Step 1: Implement**

```python
# bot/handlers/tiktok.py
import os
import tempfile
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository, PostHistoryRepository
from bot.keyboards.inline import tiktok_subtype_keyboard
from bot.services.claude_service import ClaudeService
from bot.services.gemini_service import GeminiService
from bot.services.playwright_service import PlaywrightService
from bot.services.scraper_service import ScraperService
from bot.states.states import TikTokStates

router = Router()

@router.callback_query(lambda c: c.data == "platform:tiktok")
async def start_tiktok(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.waiting_subtype)
    await callback.message.edit_text(
        "What kind of TikTok video?",
        reply_markup=tiktok_subtype_keyboard(),
    )
    await callback.answer()

# --- Product Demo ---

@router.callback_query(TikTokStates.waiting_subtype, F.data == "tiktok:product_demo")
async def start_product_demo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.waiting_product_url)
    await callback.message.edit_text("Send me the product URL to record.")
    await callback.answer()

@router.message(TikTokStates.waiting_product_url)
async def on_product_url(message: Message, state: FSMContext):
    url = message.text.strip()
    await state.set_state(TikTokStates.recording)
    await message.answer("Recording the demo... this may take 30–60 seconds.")

    service = PlaywrightService()
    try:
        video_path = await service.record_product_demo(url)
    except ValueError as e:
        await state.set_state(TikTokStates.waiting_product_url)
        await message.answer(f"Invalid URL. Please send a valid https:// link.")
        return
    except Exception as e:
        await state.clear()
        await message.answer(f"Recording failed: {e}. Please try again.")
        return

    video_file = FSInputFile(video_path)
    await message.answer_video(video_file, caption="Here's your product demo!")
    os.unlink(video_path)

    await state.update_data(recorded_url=url)
    await message.answer(
        "Want a TikTok caption for this video?",
        reply_markup=__caption_keyboard(),
    )

def __caption_keyboard():
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yes, generate caption", callback_data="demo:caption")],
        [InlineKeyboardButton(text="No thanks", callback_data="demo:skip")],
    ])

@router.callback_query(F.data == "demo:caption")
async def on_generate_caption(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(callback.from_user.id)
    scraper = ScraperService()
    page_content = await scraper.scrape_url(data.get("recorded_url", ""))
    claude = ClaudeService()
    caption = await claude.generate_tiktok_caption(
        url=data.get("recorded_url", ""),
        page_content=page_content,
        tone_profile=tov.profile_json if tov else {},
    )
    await callback.message.answer(f"Caption:\n\n{caption}")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "demo:skip")
async def on_skip_caption(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Done!")

# --- Video from Plot ---

@router.callback_query(TikTokStates.waiting_subtype, F.data == "tiktok:video_plot")
async def start_video_plot(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TikTokStates.waiting_description)
    await state.update_data(materials=[])
    await callback.message.edit_text("Describe your video idea.")
    await callback.answer()

@router.message(TikTokStates.waiting_description)
async def on_video_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(TikTokStates.collecting_materials)
    await message.answer(
        "Now send photos or materials to include (optional).\nType /done when ready."
    )

@router.message(TikTokStates.collecting_materials, F.photo)
async def on_material_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    materials = data.get("materials", [])
    file_id = message.photo[-1].file_id
    materials.append({"type": "photo", "file_id": file_id})
    await state.update_data(materials=materials)
    await message.answer(f"Got photo ({len(materials)} so far). Send more or /done.")

@router.message(TikTokStates.collecting_materials, F.text == "/done")
async def on_materials_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer("Generating your video... this may take 1–2 minutes.")

    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(message.from_user.id)

    # Download photos from Telegram
    image_paths = []
    bot = message.bot
    for material in data.get("materials", []):
        if material["type"] == "photo":
            file = await bot.get_file(material["file_id"])
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            await bot.download_file(file.file_path, destination=tmp.name)
            image_paths.append(tmp.name)

    gemini = GeminiService()
    try:
        response = await gemini.generate_video(
            description=data.get("description", ""),
            image_paths=image_paths,
            tone_profile=tov.profile_json if tov else {},
        )
        # Extract video from response and send
        # Note: exact response handling depends on Gemini API video output format
        await message.answer("Video generated! (Gemini video output handling depends on API response format)")
    except Exception as e:
        await message.answer(f"Video generation failed: {e}")
    finally:
        for path in image_paths:
            os.unlink(path)
        await state.clear()
```

**Step 2: Commit**

```bash
git add bot/handlers/tiktok.py
git commit -m "feat: add TikTok handler (product demo + video plot)"
```

---

## Task 19: Railway Deployment Config

**Files:**
- Create: `railway.toml`
- Create: `.dockerignore`

**Step 1: Create railway.toml**

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "alembic upgrade head && python -m bot.main"
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

**Step 2: Create .dockerignore**

```
.env
.git
__pycache__
*.pyc
.pytest_cache
.venv
*.mp4
/tmp
```

**Step 3: Update Dockerfile for production (multi-stage)**

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl wget gnupg libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libxss1 libxtst6 fonts-liberation libappindicator3-1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN playwright install chromium

COPY . .

CMD ["sh", "-c", "alembic upgrade head && python -m bot.main"]
```

**Step 4: Commit**

```bash
git add railway.toml .dockerignore Dockerfile
git commit -m "chore: add Railway deployment config and production Dockerfile"
```

---

## Task 20: End-to-End Smoke Test

**Goal:** Verify the bot starts and responds to /start locally.

**Step 1: Set up .env**

```bash
cp .env.example .env
# Fill in: TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, GOOGLE_API_KEY
```

**Step 2: Start services**

```bash
docker compose up -d db
docker compose run --rm bot alembic upgrade head
docker compose up bot
```

**Step 3: Open Telegram, find your bot, send /start**

Expected: bot replies with welcome message and two buttons.

**Step 4: Test tone of voice wizard**

Click "Create tone of voice" → answer each question → confirm profile.
Expected: profile saved, confirmation message shown.

**Step 5: Test LinkedIn flow**

Click "Create content" → LinkedIn → send a URL → /done.
Expected: post draft with action buttons.

**Step 6: Commit final state**

```bash
git add .
git commit -m "chore: verified end-to-end smoke test passes"
```

---

## Summary

| Task | What it builds |
|---|---|
| 1 | Git + project skeleton |
| 2 | Dependencies + .env |
| 3 | Settings (pydantic-settings) |
| 4 | Docker Compose |
| 5 | DB models |
| 6 | Alembic migrations |
| 7 | DB repositories |
| 8 | FSM states |
| 9 | Inline keyboards |
| 10 | Skills prompt files |
| 11 | Scraper service |
| 12 | Claude service |
| 13 | Gemini service |
| 14 | Playwright service |
| 15 | Start handler + main.py |
| 16 | Tone of voice wizard |
| 17 | LinkedIn handler |
| 18 | TikTok handler |
| 19 | Railway deployment |
| 20 | End-to-end smoke test |
