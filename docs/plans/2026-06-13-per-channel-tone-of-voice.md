# Per-Channel Tone of Voice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give each user one tone of voice (TOV) per channel (Instagram/TikTok/LinkedIn), show the "Create tone of voice" button only while a channel still lacks one, manage existing TOVs via `/settings`, build TOVs via wizard or a unified Apify import for all three channels, and add a full Instagram content flow (photo→caption + scenario helper → optional Reel).

**Architecture:** SQLAlchemy `ToneOfVoice` gains a `channel` column with a unique `(user_id, channel)` constraint; the repository selects by channel and upserts. A new `bot/services/tov/` package wraps the existing `ApifyClient` transport to scrape any channel's profile posts and generate a channel-tuned TOV via Claude. Aiogram handlers become channel-aware. The Veo flow currently inside `tiktok.py` is extracted into a shared `bot/handlers/_veo_flow.py` so TikTok and Instagram both drive it.

**Tech Stack:** Python 3.10, aiogram 3, SQLAlchemy 2 async + Alembic, anthropic SDK, google-genai (Gemini/Veo via Vertex), Apify REST, pytest + pytest-asyncio.

**Design doc:** `docs/plans/2026-06-13-per-channel-tone-of-voice-design.md`

**Conventions in this repo (read before starting):**
- Run a single test: `python -m pytest tests/path/test.py::test_name -v` (use the repo `.venv` Python; from the worktree call `C:/Users/aleks/Documents/Projects/social/.venv/Scripts/python.exe -m pytest ...`).
- Run all: `python -m pytest -q` (baseline is **122 passing**).
- Handler tests use hand-rolled `FakeMessage` / `FakeCallback` / `FakeFSMContext` (see `tests/handlers/test_post_writer.py`) — reuse that style; do **not** spin up a real aiogram Dispatcher.
- `conftest.py` sets env vars and `DATABASE_URL=sqlite+aiosqlite:///:memory:`.
- The three channel slugs are exactly `"instagram"`, `"tiktok"`, `"linkedin"`. Define them once (Task 1) and import everywhere — never re-hardcode the list.

---

## Phase A — Data model & repository

### Task 1: Add `channel` to the model + channel-scoped repository

**Files:**
- Modify: `bot/db/models.py:21-32` (ToneOfVoice)
- Modify: `bot/db/repository.py:19-44` (ToneOfVoiceRepository)
- Create: `bot/db/channels.py`
- Test: `tests/test_tov_repository.py`

**Step 1: Define the channel constants**

Create `bot/db/channels.py`:

```python
"""Canonical channel slugs for per-channel tone of voice."""

INSTAGRAM = "instagram"
TIKTOK = "tiktok"
LINKEDIN = "linkedin"

# Order matters: drives picker + /settings display order.
CHANNELS: tuple[str, ...] = (INSTAGRAM, TIKTOK, LINKEDIN)

CHANNEL_LABELS = {
    INSTAGRAM: "📸 Instagram",
    TIKTOK: "🎵 TikTok",
    LINKEDIN: "💼 LinkedIn",
}
```

**Step 2: Write the failing repository test**

Create `tests/test_tov_repository.py`. Use a real in-memory async engine so we exercise the unique constraint and upsert overwrite:

```python
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
    # exactly one row for that (user, channel)
    assert (await repo.get_channels_with_tov(1)) == {LINKEDIN}


@pytest.mark.asyncio
async def test_get_channels_with_tov_and_delete(session):
    repo = ToneOfVoiceRepository(session)
    await repo.upsert(1, LINKEDIN, "LI", {})
    await repo.upsert(1, INSTAGRAM, "IG", {})
    assert await repo.get_channels_with_tov(1) == {LINKEDIN, INSTAGRAM}
    await repo.delete(1, LINKEDIN)
    assert await repo.get_channels_with_tov(1) == {INSTAGRAM}
```

**Step 3: Run it to verify it fails**

Run: `python -m pytest tests/test_tov_repository.py -v`
Expected: FAIL (`channel` column / methods don't exist).

**Step 4: Update the model**

In `bot/db/models.py`, add to `ToneOfVoice` (after `name`):

```python
    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
```

And add a table arg for uniqueness (top of the class body, after `__tablename__`):

```python
    from sqlalchemy import UniqueConstraint  # move to top-level imports
    __table_args__ = (UniqueConstraint("user_id", "channel", name="uq_tov_user_channel"),)
```

(Put `UniqueConstraint` in the module-level import line, not inside the class.)

**Step 5: Rewrite the repository**

Replace `ToneOfVoiceRepository` in `bot/db/repository.py` with:

```python
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
```

Remove the old `get_active` / `deactivate_all` / `create` methods. (Consumers are fixed in Tasks 3–4.)

**Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_tov_repository.py -v`
Expected: PASS (3 tests).

**Step 7: Commit**

```bash
git add bot/db/channels.py bot/db/models.py bot/db/repository.py tests/test_tov_repository.py
git commit -m "feat: channel-scoped ToneOfVoice model + repository"
```

---

### Task 2: Alembic migration (add channel, unique index, clean slate)

**Files:**
- Create: `migrations/versions/0002_tov_channel.py`

**Step 1: Write the migration**

```python
"""per-channel tone of voice

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean slate: existing rows are not channel-tagged (design decision).
    op.execute("DELETE FROM tone_of_voices")
    with op.batch_alter_table("tone_of_voices") as batch:
        batch.add_column(sa.Column("channel", sa.String(16), nullable=False, server_default="linkedin"))
        batch.create_unique_constraint("uq_tov_user_channel", ["user_id", "channel"])
        batch.create_index("ix_tone_of_voices_channel", ["channel"])
    # Drop the temporary server_default now that the table is empty.
    with op.batch_alter_table("tone_of_voices") as batch:
        batch.alter_column("channel", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("tone_of_voices") as batch:
        batch.drop_index("ix_tone_of_voices_channel")
        batch.drop_constraint("uq_tov_user_channel", type_="unique")
        batch.drop_column("channel")
```

(SQLite needs `batch_alter_table` for constraint/column changes — that's why batch mode is used.)

**Step 2: Apply it against the local DB**

Run: `python -m alembic upgrade head`
Expected: completes without error; `tone_of_voices` now has a `channel` column.

**Step 3: Verify the column exists**

Run: `python -c "import sqlite3; print([r[1] for r in sqlite3.connect('social.db').execute('PRAGMA table_info(tone_of_voices)')])"`
Expected: list includes `'channel'`.

**Step 4: Commit**

```bash
git add migrations/versions/0002_tov_channel.py
git commit -m "feat: migration for per-channel tone of voice (clean slate)"
```

---

## Phase B — Point existing consumers at the channel lookup

These keep LinkedIn/TikTok working under the new schema before we add new UX.

### Task 3: LinkedIn shared helper → `get_for_channel`

**Files:**
- Modify: `bot/handlers/linkedin/_shared.py:40-43`
- Test: `tests/handlers/test_linkedin_shared.py`

**Step 1: Update the failing test**

In `tests/handlers/test_linkedin_shared.py`, ensure `get_active_tov` calls the repo with the LinkedIn channel. Add/adjust:

```python
@pytest.mark.asyncio
async def test_get_active_tov_uses_linkedin_channel():
    from bot.handlers.linkedin import _shared
    from bot.db.channels import LINKEDIN

    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=MagicMock(profile_json={"x": 1}))

    with patch.object(_shared, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(_shared, "async_session_factory", _fake_session_factory()):
        result = await _shared.get_active_tov(42)

    fake_repo.get_for_channel.assert_awaited_once_with(42, LINKEDIN)
    assert result == {"x": 1}
```

(`_fake_session_factory` = a context-manager mock yielding an `AsyncMock` session; copy the pattern already used elsewhere in the file, or add a small helper.)

**Step 2: Run it to verify it fails**

Run: `python -m pytest tests/handlers/test_linkedin_shared.py -v`
Expected: FAIL (`get_active` still called / method missing).

**Step 3: Implement**

In `bot/handlers/linkedin/_shared.py`:

```python
from bot.db.channels import LINKEDIN

async def get_active_tov(user_id: int) -> dict:
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_for_channel(user_id, LINKEDIN)
    return tov.profile_json if tov else {}
```

**Step 4: Run tests**

Run: `python -m pytest tests/handlers/test_linkedin_shared.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/handlers/linkedin/_shared.py tests/handlers/test_linkedin_shared.py
git commit -m "refactor: LinkedIn TOV lookup is channel-scoped"
```

---

### Task 4: TikTok handler → `get_for_channel`

**Files:**
- Modify: `bot/handlers/tiktok.py:76`, `:149`, `:230` (the three `get_active` call sites)
- Test: `tests/handlers/test_tiktok.py` (create if absent)

**Step 1: Write a failing test**

Create `tests/handlers/test_tiktok.py` covering the caption path's TOV lookup:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import tiktok
from bot.db.channels import TIKTOK
# reuse Fake* helpers (copy from test_post_writer or import a shared module)

@pytest.mark.asyncio
async def test_caption_uses_tiktok_channel():
    state = FakeFSMContext({"recorded_url": "http://x"})
    callback = FakeCallback(data="demo:caption")

    fake_repo = MagicMock()
    fake_repo.get_for_channel = AsyncMock(return_value=None)

    with patch.object(tiktok, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tiktok, "async_session_factory", _fake_session_factory()), \
         patch.object(tiktok, "ScraperService") as Scr, \
         patch.object(tiktok, "ClaudeService") as Cl:
        Scr.return_value.scrape_url = AsyncMock(return_value="page")
        Cl.return_value.generate_tiktok_caption = AsyncMock(return_value="CAP")
        await tiktok.on_generate_caption(callback, state)

    fake_repo.get_for_channel.assert_awaited_with(callback.from_user.id, TIKTOK)
```

(Lift `Fake*` + `_fake_session_factory` into `tests/handlers/_fakes.py` and import from there to stay DRY — do this once and reuse across handler tests.)

**Step 2: Run it to verify it fails**

Run: `python -m pytest tests/handlers/test_tiktok.py -v`
Expected: FAIL.

**Step 3: Implement**

In `bot/handlers/tiktok.py`, add `from bot.db.channels import TIKTOK` and replace all three:

```python
tov = await ToneOfVoiceRepository(session).get_active(...)
```
with:
```python
tov = await ToneOfVoiceRepository(session).get_for_channel(..., TIKTOK)
```

**Step 4: Run tests**

Run: `python -m pytest tests/handlers/test_tiktok.py -v`
Expected: PASS.

**Step 5: Full suite (catch the schema/consumer break)**

Run: `python -m pytest -q`
Expected: all green (fix any test still referencing `get_active`/`create` on the repo).

**Step 6: Commit**

```bash
git add bot/handlers/tiktok.py tests/handlers/test_tiktok.py tests/handlers/_fakes.py
git commit -m "refactor: TikTok TOV lookup is channel-scoped"
```

---

## Phase C — Unified Apify TOV import layer

### Task 5: Channel→actor config + handle extraction

**Files:**
- Create: `bot/services/tov/__init__.py`
- Create: `bot/services/tov/config.py`
- Create: `bot/services/tov/handles.py`
- Test: `tests/services/tov/test_handles.py`

**Step 1: Write the failing handle test**

```python
import pytest
from bot.services.tov.handles import extract_handle
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN

@pytest.mark.parametrize("channel,raw,expected", [
    (INSTAGRAM, "@alex", "alex"),
    (INSTAGRAM, "https://instagram.com/alex/", "alex"),
    (TIKTOK, "@alex", "alex"),
    (TIKTOK, "https://www.tiktok.com/@alex?lang=en", "alex"),
    (LINKEDIN, "https://www.linkedin.com/in/alex-smith/", "alex-smith"),
    (LINKEDIN, "alex-smith", "alex-smith"),
])
def test_extract_handle(channel, raw, expected):
    assert extract_handle(channel, raw) == expected

def test_extract_handle_empty_raises():
    with pytest.raises(ValueError):
        extract_handle(INSTAGRAM, "   ")
```

**Step 2: Run it to verify it fails**

Run: `python -m pytest tests/services/tov/test_handles.py -v`
Expected: FAIL (module missing). Also create empty `tests/services/tov/__init__.py`.

**Step 3: Implement config + handles**

`bot/services/tov/config.py`:

```python
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN

# Public, no-cookies Apify actors that return a profile's recent posts.
CHANNEL_ACTORS = {
    INSTAGRAM: "apify~instagram-scraper",
    TIKTOK: "clockworks~tiktok-scraper",
    LINKEDIN: "apimaestro~linkedin-profile-posts",
}

# Per-channel actor input builder: (handle, limit) -> dict payload.
def actor_input(channel: str, handle: str, limit: int) -> dict:
    if channel == INSTAGRAM:
        return {
            "directUrls": [f"https://www.instagram.com/{handle}/"],
            "resultsType": "posts", "resultsLimit": limit, "addParentData": False,
        }
    if channel == TIKTOK:
        return {"profiles": [handle], "resultsPerPage": limit, "shouldDownloadVideos": False}
    if channel == LINKEDIN:
        return {"username": handle, "limit": limit}
    raise ValueError(f"unknown channel: {channel}")

# Per-channel: extract the caption/body text from one actor result item.
def post_text(channel: str, item: dict) -> str:
    if channel == INSTAGRAM:
        return (item.get("caption") or "").strip()
    if channel == TIKTOK:
        return (item.get("text") or item.get("description") or "").strip()
    if channel == LINKEDIN:
        return (item.get("text") or item.get("content") or "").strip()
    raise ValueError(f"unknown channel: {channel}")
```

> **Note for implementer:** the TikTok/LinkedIn actor field names above are best-guess; verify against one real Apify run and adjust `actor_input`/`post_text`. Keep this the *only* place field shapes live.

`bot/services/tov/handles.py`:

```python
import re
from bot.db.channels import INSTAGRAM, TIKTOK, LINKEDIN

_PATTERNS = {
    INSTAGRAM: r"instagram\.com/([^/?&#]+)",
    TIKTOK: r"tiktok\.com/@([^/?&#]+)",
    LINKEDIN: r"linkedin\.com/in/([^/?&#]+)",
}

def extract_handle(channel: str, raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty handle")
    pat = _PATTERNS.get(channel)
    if pat:
        m = re.search(pat, raw)
        if m:
            return m.group(1).strip("/")
    return raw.lstrip("@").strip("/")
```

**Step 4: Run tests**

Run: `python -m pytest tests/services/tov/test_handles.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add bot/services/tov/ tests/services/tov/
git commit -m "feat: TOV import channel config + handle extraction"
```

---

### Task 6: Generalized preprocessing

**Files:**
- Create: `bot/services/tov/preprocess.py`
- Test: `tests/services/tov/test_preprocess.py`

**Step 1: Write the failing test**

```python
from bot.services.tov.preprocess import preprocess_posts
from bot.db.channels import INSTAGRAM

def test_preprocess_filters_empty_and_counts():
    posts = [{"caption": "Привет мир"}, {"caption": ""}, {"caption": "Hello world"}]
    data = preprocess_posts(INSTAGRAM, posts)
    assert data["posts_with_text"] == 2
    assert data["total_posts"] == 3
    assert data["avg_text_length"] > 0
    langs = data["language_counts"]
    assert langs["ru"] == 1 and langs["en"] == 1
```

**Step 2: Run it to verify it fails**

Run: `python -m pytest tests/services/tov/test_preprocess.py -v`
Expected: FAIL.

**Step 3: Implement** (lift + generalize `_detect_language` / `_preprocess_posts` from `bot/services/instagram_tov_service.py`, but read text via `config.post_text`):

```python
from bot.services.tov.config import post_text

def detect_language(text: str) -> str:
    if not text:
        return "ru"
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return "ru"
    cyrillic = sum(1 for c in alpha if "Ѐ" <= c <= "ӿ")
    ratio = cyrillic / len(alpha)
    if ratio > 0.6:
        return "ru"
    if ratio < 0.2:
        return "en"
    return "mixed"

def preprocess_posts(channel: str, posts: list[dict]) -> dict:
    texts = []
    for p in posts:
        t = post_text(channel, p)
        if t:
            texts.append({"text": t, "lang": detect_language(t), "likes": p.get("likesCount", 0)})
    lengths = [len(t["text"]) for t in texts]
    counts = {"ru": 0, "en": 0, "mixed": 0}
    for t in texts:
        counts[t["lang"]] = counts.get(t["lang"], 0) + 1
    return {
        "total_posts": len(posts),
        "posts_with_text": len(texts),
        "avg_text_length": int(sum(lengths) / len(lengths)) if lengths else 0,
        "language_counts": counts,
        "texts": texts,
    }
```

**Step 4: Run tests** → PASS.

**Step 5: Commit**

```bash
git add bot/services/tov/preprocess.py tests/services/tov/test_preprocess.py
git commit -m "feat: generalized TOV post preprocessing"
```

---

### Task 7: `TovImportService` (transport + Claude generation)

**Files:**
- Create: `bot/services/tov/service.py`
- Create: `bot/services/tov/prompts.py`
- Create: `bot/services/tov/errors.py`
- Test: `tests/services/tov/test_service.py`

**Step 1: Errors**

`bot/services/tov/errors.py`:

```python
class PrivateProfileError(Exception): ...
class NoPostsError(Exception): ...
class ServiceError(Exception): ...
```

**Step 2: Write the failing service test** (mock the Apify transport + Claude; no network):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.tov.service import TovImportService
from bot.services.tov.errors import NoPostsError
from bot.db.channels import TIKTOK

@pytest.mark.asyncio
async def test_analyze_returns_tov_dict():
    svc = TovImportService(apify_token="t", anthropic_api_key="k")
    fake_client = MagicMock()
    fake_client.fetch_profile_posts = MagicMock(return_value=[{"text": "hi there"}])

    with patch.object(svc, "_client", fake_client), \
         patch("bot.services.tov.service._generate_tov", return_value={"dos": ["x"]}):
        result = await svc.analyze(TIKTOK, "@alex")

    assert result["channel"] == TIKTOK
    assert result["handle"] == "alex"
    assert result["dos"] == ["x"]

@pytest.mark.asyncio
async def test_analyze_no_posts_raises():
    svc = TovImportService(apify_token="t", anthropic_api_key="k")
    fake_client = MagicMock()
    fake_client.fetch_profile_posts = MagicMock(return_value=[])
    with patch.object(svc, "_client", fake_client):
        with pytest.raises(NoPostsError):
            await svc.analyze(TIKTOK, "@alex")
```

**Step 3: Run it to verify it fails** → FAIL.

**Step 4: Extend `ApifyClient` with profile-post fetching**

In `bot/services/linkedin/apify_client.py`, add a generic method:

```python
    def fetch_profile_posts(self, actor_id: str, payload: dict, *, force_refresh: bool = False) -> list[dict]:
        """Run any profile-posts actor and return its dataset items."""
        return self._run_sync(actor_id, payload, force_refresh=force_refresh)
```

**Step 5: Implement the service + prompt**

`bot/services/tov/prompts.py` — one channel-tuned prompt builder returning the system text + JSON schema per channel (keep IG's existing rich schema for IG; lighter hook/CTA-focused schemas for TikTok/LinkedIn). Model the prompt body on `instagram_tov_service._build_prompt`.

`bot/services/tov/service.py`:

```python
import json, re, anthropic
from bot.services.linkedin.apify_client import ApifyClient, ApifyError
from bot.services.tov.config import CHANNEL_ACTORS, actor_input
from bot.services.tov.handles import extract_handle
from bot.services.tov.preprocess import preprocess_posts
from bot.services.tov.prompts import build_tov_prompt
from bot.services.tov.errors import NoPostsError, ServiceError

def _generate_tov(channel, handle, data, anthropic_api_key) -> dict:
    prompt = build_tov_prompt(channel, handle, data)
    client = anthropic.Anthropic(api_key=anthropic_api_key)
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=4096,
                                 messages=[{"role": "user", "content": prompt}])
    text = msg.content[0].text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)

class TovImportService:
    def __init__(self, apify_token: str, anthropic_api_key: str, limit: int = 50):
        self._client = ApifyClient(token=apify_token)
        self._anthropic_api_key = anthropic_api_key
        self._limit = limit

    async def analyze(self, channel: str, raw_handle: str) -> dict:
        import asyncio
        handle = extract_handle(channel, raw_handle)
        try:
            posts = await asyncio.to_thread(
                self._client.fetch_profile_posts,
                CHANNEL_ACTORS[channel], actor_input(channel, handle, self._limit),
            )
        except ApifyError as e:
            raise ServiceError(str(e)) from e
        if not posts:
            raise NoPostsError("no posts found")
        data = preprocess_posts(channel, posts)
        if data["posts_with_text"] == 0:
            raise NoPostsError("no posts with text")
        try:
            tov = await asyncio.to_thread(_generate_tov, channel, handle, data, self._anthropic_api_key)
        except Exception as e:
            raise ServiceError(str(e)) from e
        tov["channel"] = channel
        tov["handle"] = handle
        tov["posts_analyzed"] = data["total_posts"]
        return tov
```

**Step 6: Run tests** → PASS.

**Step 7: Commit**

```bash
git add bot/services/tov/ bot/services/linkedin/apify_client.py tests/services/tov/test_service.py
git commit -m "feat: unified Apify TOV import service for all channels"
```

---

### Task 8: Refactor Instagram TOV service onto the shared transport

**Files:**
- Modify: `bot/services/instagram_tov_service.py`
- Test: `tests/services/test_instagram_tov_service.py` (must stay green)

**Step 1: Run the existing IG test to capture current behavior**

Run: `python -m pytest tests/services/test_instagram_tov_service.py -v`
Expected: PASS (baseline).

**Step 2: Make `InstagramTovService` delegate to `TovImportService`**

Keep the public class + error names (re-export from `bot.services.tov.errors`) so `bot/handlers/tone_of_voice.py` imports don't break:

```python
from bot.services.tov.errors import PrivateProfileError, NoPostsError, ServiceError
from bot.services.tov.service import TovImportService
from bot.db.channels import INSTAGRAM

class InstagramTovService:
    def __init__(self, apify_token: str, anthropic_api_key: str):
        self._svc = TovImportService(apify_token, anthropic_api_key)

    async def analyze(self, username: str) -> dict:
        result = await self._svc.analyze(INSTAGRAM, username)
        result["username"] = result.get("handle")  # back-compat key
        return result
```

(If the existing test asserts on the old hand-rolled internals, update it to mock `TovImportService.analyze` instead — behavior, not implementation.)

**Step 3: Run tests** → PASS (IG test + formatter test).

**Step 4: Commit**

```bash
git add bot/services/instagram_tov_service.py tests/services/test_instagram_tov_service.py
git commit -m "refactor: Instagram TOV rides the shared Apify transport"
```

---

## Phase D — Channel-scoped creation UX + /settings

### Task 9: Keyboards become channel-aware

**Files:**
- Modify: `bot/keyboards/inline.py`
- Test: `tests/test_keyboards.py`

**Step 1: Write failing keyboard tests**

```python
from bot.keyboards.inline import (
    main_menu_keyboard, tov_channel_picker_keyboard, settings_keyboard, tov_method_keyboard,
)
from bot.db.channels import CHANNELS, INSTAGRAM, TIKTOK, LINKEDIN

def _labels(kb):
    return [b.text for row in kb.inline_keyboard for b in row]

def test_main_menu_shows_create_tov_when_channel_missing():
    kb = main_menu_keyboard(channels_with_tov={LINKEDIN})
    assert any("tone of voice" in t.lower() for t in _labels(kb))

def test_main_menu_hides_create_tov_when_all_present():
    kb = main_menu_keyboard(channels_with_tov=set(CHANNELS))
    assert not any("tone of voice" in t.lower() for t in _labels(kb))

def test_picker_lists_only_missing_channels():
    kb = tov_channel_picker_keyboard(channels_with_tov={LINKEDIN})
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "tovchan:instagram" in data and "tovchan:tiktok" in data
    assert "tovchan:linkedin" not in data

def test_method_keyboard_carries_channel():
    kb = tov_method_keyboard(INSTAGRAM)
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "tovm:wizard:instagram" in data and "tovm:import:instagram" in data

def test_settings_shows_status_per_channel():
    kb = settings_keyboard(channels_with_tov={INSTAGRAM})
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "settings:delete:instagram" in data       # created → delete/edit
    assert "settings:create:tiktok" in data           # missing → create
```

**Step 2: Run** → FAIL.

**Step 3: Implement** in `bot/keyboards/inline.py`:

```python
from bot.db.channels import CHANNELS, CHANNEL_LABELS

def main_menu_keyboard(channels_with_tov: set[str] | None = None) -> InlineKeyboardMarkup:
    channels_with_tov = channels_with_tov or set()
    rows = []
    if set(channels_with_tov) != set(CHANNELS):
        rows.append([InlineKeyboardButton(text="🎭 Create tone of voice", callback_data="action:tone_of_voice")])
    rows.append([InlineKeyboardButton(text="✍️ Create content", callback_data="action:create_content")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def tov_channel_picker_keyboard(channels_with_tov: set[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=CHANNEL_LABELS[c], callback_data=f"tovchan:{c}")]
        for c in CHANNELS if c not in channels_with_tov
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def tov_method_keyboard(channel: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧙 Answer a few questions", callback_data=f"tovm:wizard:{channel}")],
        [InlineKeyboardButton(text="📥 Import from my profile", callback_data=f"tovm:import:{channel}")],
    ])

def settings_keyboard(channels_with_tov: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for c in CHANNELS:
        if c in channels_with_tov:
            rows.append([
                InlineKeyboardButton(text=f"{CHANNEL_LABELS[c]} · ✏️ Recreate", callback_data=f"settings:create:{c}"),
                InlineKeyboardButton(text="🗑 Delete", callback_data=f"settings:delete:{c}"),
            ])
        else:
            rows.append([InlineKeyboardButton(text=f"{CHANNEL_LABELS[c]} · ➕ Create", callback_data=f"settings:create:{c}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

Delete the old no-arg `tov_method_keyboard()` (Task 11 updates its caller). Note `main_menu_keyboard` now takes an arg — Task 10 updates callers.

**Step 4: Run** → PASS.

**Step 5: Commit**

```bash
git add bot/keyboards/inline.py tests/test_keyboards.py
git commit -m "feat: channel-aware menu, picker, method, and settings keyboards"
```

---

### Task 10: `/start` queries TOV set and renders conditionally

**Files:**
- Modify: `bot/handlers/start.py`
- Test: `tests/handlers/test_start.py` (create)

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_start_hides_button_when_all_channels_have_tov():
    from bot.handlers import start
    from bot.db.channels import CHANNELS
    message = FakeMessage()
    fake_user_repo = MagicMock(); fake_user_repo.get_or_create = AsyncMock()
    fake_tov_repo = MagicMock(); fake_tov_repo.get_channels_with_tov = AsyncMock(return_value=set(CHANNELS))
    with patch.object(start, "UserRepository", return_value=fake_user_repo), \
         patch.object(start, "ToneOfVoiceRepository", return_value=fake_tov_repo), \
         patch.object(start, "async_session_factory", _fake_session_factory()):
        await start.cmd_start(message)
    kb = message.answer.await_args.kwargs["reply_markup"]
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert not any("tone of voice" in t.lower() for t in labels)
```

**Step 2: Run** → FAIL.

**Step 3: Implement** `cmd_start`:

```python
from bot.db.repository import UserRepository, ToneOfVoiceRepository

async def cmd_start(message: Message):
    async with async_session_factory() as session:
        await UserRepository(session).get_or_create(
            telegram_id=message.from_user.id, username=message.from_user.username)
        await session.commit()
        channels = await ToneOfVoiceRepository(session).get_channels_with_tov(message.from_user.id)
    await message.answer(
        "👋 Welcome! I help you create content for Instagram, LinkedIn, and TikTok.\n\n"
        "What would you like to do?",
        reply_markup=main_menu_keyboard(channels_with_tov=channels),
    )
```

**Step 4: Run** → PASS.

**Step 5: Commit**

```bash
git add bot/handlers/start.py tests/handlers/test_start.py
git commit -m "feat: /start shows Create-TOV button only when a channel lacks one"
```

---

### Task 11: Channel-scoped TOV creation (picker → method → save)

**Files:**
- Modify: `bot/handlers/tone_of_voice.py`
- Modify: `bot/states/states.py` (add `choosing_channel` to `ToneOfVoiceStates`)
- Test: `tests/handlers/test_tone_of_voice.py` (create)

**Step 1: Add state**

In `bot/states/states.py`, add to `ToneOfVoiceStates`: `choosing_channel = State()`.

**Step 2: Write failing tests** for the new wiring:

```python
@pytest.mark.asyncio
async def test_choose_method_shows_channel_picker():
    from bot.handlers import tone_of_voice as tov
    callback = FakeCallback(data="action:tone_of_voice")
    state = FakeFSMContext()
    fake_repo = MagicMock(); fake_repo.get_channels_with_tov = AsyncMock(return_value=set())
    with patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", _fake_session_factory()):
        await tov.on_create_tov(callback, state)
    assert state.state == tov.ToneOfVoiceStates.choosing_channel

@pytest.mark.asyncio
async def test_picked_channel_is_stored_and_method_shown():
    from bot.handlers import tone_of_voice as tov
    from bot.db.channels import INSTAGRAM
    callback = FakeCallback(data="tovchan:instagram")
    state = FakeFSMContext()
    await tov.on_channel_picked(callback, state)
    assert (await state.get_data())["channel"] == INSTAGRAM

@pytest.mark.asyncio
async def test_wizard_save_upserts_for_channel():
    from bot.handlers import tone_of_voice as tov
    from bot.db.channels import TIKTOK
    state = FakeFSMContext({"channel": TIKTOK, "generated_profile": {"x": 1}, "role": "coach"})
    callback = FakeCallback(data="tov:save")
    fake_repo = MagicMock(); fake_repo.upsert = AsyncMock()
    with patch.object(tov, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(tov, "async_session_factory", _fake_session_factory()):
        await tov.on_save_profile(callback, state)
    args, kwargs = fake_repo.upsert.call_args
    assert TIKTOK in args or kwargs.get("channel") == TIKTOK
```

**Step 3: Run** → FAIL.

**Step 4: Implement the rewiring** in `bot/handlers/tone_of_voice.py`:

- Rename entry handler to `on_create_tov` (still bound to `action:tone_of_voice`): load `get_channels_with_tov`, set state `choosing_channel`, send `tov_channel_picker_keyboard(channels)`.
- New handler `on_channel_picked` bound to `F.data.startswith("tovchan:")`: parse channel, `state.update_data(channel=...)`, set state `choosing_method`, send `tov_method_keyboard(channel)`.
- Update method handlers to match the new callbacks `tovm:wizard:<channel>` / `tovm:import:<channel>` (parse channel from callback OR read from state).
- **Import path** now uses `TovImportService.analyze(channel, handle)` (not IG-only), with channel-appropriate "send your @handle / profile URL" copy.
- All save sites call `repo.upsert(user_id, channel, name, profile_json)` where `channel = (await state.get_data())["channel"]`. `name` = e.g. `f"{CHANNEL_LABELS[channel]} voice"`.
- After save, reload `get_channels_with_tov`; if channels remain, re-show the picker ("✅ Saved. Set up another?"); else send the main menu via `main_menu_keyboard(channels)`.

Keep the wizard Q&A steps unchanged except they now carry `channel` in FSM data.

**Step 5: Run** the new tests + full suite → PASS.

**Step 6: Commit**

```bash
git add bot/handlers/tone_of_voice.py bot/states/states.py tests/handlers/test_tone_of_voice.py
git commit -m "feat: channel-scoped TOV creation (picker -> method -> upsert)"
```

---

### Task 12: `/settings` command

**Files:**
- Create: `bot/handlers/settings.py`
- Modify: `bot/main.py:16,35-39` (import + register router)
- Test: `tests/handlers/test_settings.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_settings_lists_channels():
    from bot.handlers import settings as st
    from bot.db.channels import INSTAGRAM
    message = FakeMessage(text="/settings")
    fake_repo = MagicMock(); fake_repo.get_channels_with_tov = AsyncMock(return_value={INSTAGRAM})
    with patch.object(st, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(st, "async_session_factory", _fake_session_factory()):
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
         patch.object(st, "async_session_factory", _fake_session_factory()):
        await st.on_settings_delete(callback, None)
    fake_repo.delete.assert_awaited_once()
    args, kwargs = fake_repo.delete.call_args
    assert LINKEDIN in args or kwargs.get("channel") == LINKEDIN
```

**Step 2: Run** → FAIL.

**Step 3: Implement** `bot/handlers/settings.py`:

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.keyboards.inline import settings_keyboard

router = Router()

async def _channels(user_id: int) -> set[str]:
    async with async_session_factory() as session:
        return await ToneOfVoiceRepository(session).get_channels_with_tov(user_id)

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    channels = await _channels(message.from_user.id)
    await message.answer("Your tone of voice per channel:", reply_markup=settings_keyboard(channels))

@router.callback_query(F.data.startswith("settings:delete:"))
async def on_settings_delete(callback: CallbackQuery, state: FSMContext):
    channel = callback.data.split(":")[2]
    async with async_session_factory() as session:
        repo = ToneOfVoiceRepository(session)
        await repo.delete(callback.from_user.id, channel)
        await session.commit()
        channels = await repo.get_channels_with_tov(callback.from_user.id)
    await callback.message.edit_text("Updated.", reply_markup=settings_keyboard(channels))
    await callback.answer("Deleted.")

# settings:create:<channel> reuses the TOV creation flow: set channel in state,
# set ToneOfVoiceStates.choosing_method, send tov_method_keyboard(channel).
@router.callback_query(F.data.startswith("settings:create:"))
async def on_settings_create(callback: CallbackQuery, state: FSMContext):
    from bot.states.states import ToneOfVoiceStates
    from bot.keyboards.inline import tov_method_keyboard
    channel = callback.data.split(":")[2]
    await state.update_data(channel=channel)
    await state.set_state(ToneOfVoiceStates.choosing_method)
    await callback.message.edit_text("How would you like to define it?",
                                     reply_markup=tov_method_keyboard(channel))
    await callback.answer()
```

Register in `bot/main.py`: add `settings` to the handlers import and `dp.include_router(settings.router)`.

**Step 4: Run** new tests + full suite → PASS.

**Step 5: Commit**

```bash
git add bot/handlers/settings.py bot/main.py tests/handlers/test_settings.py
git commit -m "feat: /settings to view, recreate, and delete per-channel TOVs"
```

---

## Phase E — Instagram content flow

### Task 13: Extract the shared Veo flow

**Files:**
- Create: `bot/handlers/_veo_flow.py`
- Modify: `bot/handlers/tiktok.py` (move the Veo handlers out; `video_plot` enters the shared flow)
- Modify: `bot/states/states.py` (add `VeoStates`)
- Test: `tests/handlers/test_veo_flow.py`

**Step 1: Add `VeoStates`** mirroring the Veo-related TikTok states:

```python
class VeoStates(StatesGroup):
    choosing_video_mode = State()
    waiting_description = State()
    collecting_materials = State()
    reviewing_prompt = State()
    editing_prompt = State()
    refining_prompt = State()
    generating_veo = State()
```

**Step 2: Write a failing test** that the shared flow reads `channel` from FSM for its TOV lookup:

```python
@pytest.mark.asyncio
async def test_veo_refine_uses_channel_from_state():
    from bot.handlers import _veo_flow
    from bot.db.channels import INSTAGRAM
    state = FakeFSMContext({"channel": INSTAGRAM, "prompts": ["p"], "video_mode": "quick", "refine_context": ""})
    message = FakeMessage(text="make it brighter")
    fake_repo = MagicMock(); fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(_veo_flow, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(_veo_flow, "async_session_factory", _fake_session_factory()), \
         patch.object(_veo_flow, "GeminiService") as G:
        G.return_value.refine_veo_prompt = AsyncMock(return_value={"kind": "revision", "prompts": ["p2"]})
        await _veo_flow.on_prompt_refine_instruction(message, state)
    fake_repo.get_for_channel.assert_awaited_with(message.from_user.id, INSTAGRAM)
```

**Step 3: Run** → FAIL.

**Step 4: Move the flow**

Cut these from `tiktok.py` into `bot/handlers/_veo_flow.py`, rebinding every `TikTokStates.*` to `VeoStates.*`: `on_video_mode`, `on_video_description`, `on_material_photo`, `_download_photos`, `on_materials_done`, `on_prompt_edit`, `on_prompt_edited`, `on_prompt_refine`, `on_prompt_refine_instruction`, `on_prompt_accept`, `_cleanup_photos`, `_show_prompt_review`, `_run_veo`. Define a `router = Router()` there.

Change the TOV lookups inside (`get_active`/`get_for_channel(..., TIKTOK)`) to read channel from state:

```python
channel = (await state.get_data()).get("channel", TIKTOK)
tov = await ToneOfVoiceRepository(session).get_for_channel(message.from_user.id, channel)
```

Add an entry helper the channels call:

```python
async def start_veo_flow(callback, state, *, channel: str):
    await state.update_data(channel=channel)
    await state.set_state(VeoStates.choosing_video_mode)
    await callback.message.edit_text("What kind of video?", reply_markup=video_mode_keyboard())
    await callback.answer()
```

In `tiktok.py`, `start_video_plot` now does `await start_veo_flow(callback, state, channel=TIKTOK)`. Register `_veo_flow.router` in `bot/main.py` (before/after tiktok — order doesn't matter, states are distinct). `_run_veo` keeps `data.get("video_mode")`; `PostHistory.platform` uses `data["channel"]` if you record history there.

**Step 5: Run** the new test + full suite. Fix any TikTok test that referenced the moved handlers (point them at `_veo_flow`). Expected: PASS.

**Step 6: Commit**

```bash
git add bot/handlers/_veo_flow.py bot/handlers/tiktok.py bot/states/states.py bot/main.py tests/handlers/test_veo_flow.py tests/handlers/test_tiktok.py
git commit -m "refactor: extract shared Veo flow, parametrized by channel"
```

---

### Task 14: Gemini caption-from-photos (vision)

**Files:**
- Modify: `bot/services/gemini_service.py`
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write failing test** (mock the genai client; assert the caption system prompt + images are passed):

```python
@pytest.mark.asyncio
async def test_caption_from_photos_calls_generate(tmp_path, monkeypatch):
    from bot.services.gemini_service import GeminiService
    svc = GeminiService()
    called = {}
    async def fake_generate(description, image_paths, system_prompt):
        called["images"] = image_paths
        called["system"] = system_prompt
        return "Sunset vibes 🌅 #travel"
    monkeypatch.setattr(svc, "_generate", fake_generate)
    img = tmp_path / "a.jpg"; img.write_bytes(b"x")
    out = await svc.caption_from_photos([str(img)], {"dos": ["short"]})
    assert "Sunset" in out
    assert called["images"] == [str(img)]
    assert "caption" in called["system"].lower()
```

**Step 2: Run** → FAIL.

**Step 3: Implement** in `GeminiService`:

```python
    def _caption_system(self, tone_profile: dict) -> str:
        return (
            "You are writing an Instagram caption for the attached photo(s). "
            "Look at what is actually in the images and write a caption that fits them. "
            "Keep it natural, add 3-6 relevant hashtags at the end. "
            "Output only the caption text. "
            f"Match this tone of voice: {json.dumps(tone_profile)}"
        )

    async def caption_from_photos(self, image_paths: list[str], tone_profile: dict) -> str:
        system_prompt = self._caption_system(tone_profile)
        text = await self._generate(
            "Write an Instagram caption for these photos.", image_paths, system_prompt)
        return text.strip()
```

**Step 4: Run** → PASS.

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: Gemini vision caption-from-photos for Instagram"
```

---

### Task 15: Instagram scenario helper (clarify-loop) service method

**Files:**
- Modify: `bot/services/gemini_service.py`
- Test: `tests/services/test_gemini_service.py`

**Step 1: Write failing test** (mirror `refine_veo_prompt`'s discriminated return):

```python
@pytest.mark.asyncio
async def test_develop_scenario_returns_clarify(monkeypatch):
    from bot.services.gemini_service import GeminiService
    svc = GeminiService()
    async def fake_json(text, system):
        return {"kind": "clarify", "question": "Who is the audience?"}
    monkeypatch.setattr(svc, "_generate_json", fake_json)
    out = await svc.develop_instagram_scenario("a reel about coffee", "", {})
    assert out == {"kind": "clarify", "question": "Who is the audience?"}

@pytest.mark.asyncio
async def test_develop_scenario_returns_script(monkeypatch):
    from bot.services.gemini_service import GeminiService
    svc = GeminiService()
    async def fake_json(text, system):
        return {"kind": "script", "script": "HOOK...\nBEATS...", "caption": "c"}
    monkeypatch.setattr(svc, "_generate_json", fake_json)
    out = await svc.develop_instagram_scenario("coffee reel", "ctx", {})
    assert out["kind"] == "script" and "HOOK" in out["script"]
```

**Step 2: Run** → FAIL.

**Step 3: Implement** a `_scenario_system(...)` returning the JSON-shape instruction (`{"kind":"script","script":...,"caption":...}` or `{"kind":"clarify","question":...}`) plus the conversation context and tone profile, and:

```python
    async def develop_instagram_scenario(self, idea: str, history: str, tone_profile: dict) -> dict:
        system = self._scenario_system(history, tone_profile)
        raw = await self._generate_json(idea, system)
        kind = raw.get("kind")
        if kind == "clarify":
            q = (raw.get("question") or "").strip()
            if not q:
                raise ValueError("clarify missing question")
            return {"kind": "clarify", "question": q}
        if kind == "script":
            script = (raw.get("script") or "").strip()
            if not script:
                raise ValueError("script missing")
            return {"kind": "script", "script": script, "caption": (raw.get("caption") or "").strip()}
        raise ValueError(f"unknown scenario kind: {kind!r}")
```

**Step 4: Run** → PASS.

**Step 5: Commit**

```bash
git add bot/services/gemini_service.py tests/services/test_gemini_service.py
git commit -m "feat: Instagram scenario helper (clarify|script) generation"
```

---

### Task 16: Instagram handler + wiring

**Files:**
- Create: `bot/handlers/instagram.py`
- Modify: `bot/states/states.py` (add `InstagramStates`)
- Modify: `bot/keyboards/inline.py` (add Instagram to `platform_keyboard`, add `instagram_subtype_keyboard`, a "Generate Reel" keyboard)
- Modify: `bot/main.py` (import + register `instagram.router`)
- Test: `tests/handlers/test_instagram.py`

**Step 1: Add states**

```python
class InstagramStates(StatesGroup):
    waiting_subtype = State()
    collecting_caption_photos = State()
    scenario_developing = State()
    scenario_ready = State()
```

**Step 2: Add keyboards**

```python
def platform_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Instagram", callback_data="platform:instagram")],
        [InlineKeyboardButton(text="💼 LinkedIn post", callback_data="platform:linkedin")],
        [InlineKeyboardButton(text="🎵 TikTok video", callback_data="platform:tiktok")],
    ])

def instagram_subtype_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Caption from photos", callback_data="ig:caption")],
        [InlineKeyboardButton(text="🎬 Scenario helper", callback_data="ig:scenario")],
    ])

def ig_generate_reel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Generate Reel", callback_data="ig:reel")],
        [InlineKeyboardButton(text="✅ Keep script only", callback_data="ig:script_done")],
    ])
```

**Step 3: Write failing handler tests** (subtype entry, caption flow uses IG channel + vision, scenario clarify loops, scenario → Generate Reel enters the shared Veo flow):

```python
@pytest.mark.asyncio
async def test_platform_instagram_shows_subtypes():
    from bot.handlers import instagram as ig
    callback = FakeCallback(data="platform:instagram")
    state = FakeFSMContext()
    await ig.start_instagram(callback, state)
    assert state.state == ig.InstagramStates.waiting_subtype

@pytest.mark.asyncio
async def test_caption_flow_uses_ig_channel_and_vision(tmp_path):
    from bot.handlers import instagram as ig
    from bot.db.channels import INSTAGRAM
    state = FakeFSMContext({"caption_photos": [{"file_id": "f"}]})
    message = FakeMessage(text="/done")
    message.bot = MagicMock()
    fake_repo = MagicMock(); fake_repo.get_for_channel = AsyncMock(return_value=None)
    with patch.object(ig, "ToneOfVoiceRepository", return_value=fake_repo), \
         patch.object(ig, "async_session_factory", _fake_session_factory()), \
         patch.object(ig, "_download_photos", new=AsyncMock(return_value=["/tmp/a.jpg"])), \
         patch.object(ig, "GeminiService") as G:
        G.return_value.caption_from_photos = AsyncMock(return_value="CAP #x")
        await ig.on_caption_photos_done(message, state)
    fake_repo.get_for_channel.assert_awaited_with(message.from_user.id, INSTAGRAM)

@pytest.mark.asyncio
async def test_scenario_clarify_stays_in_state():
    from bot.handlers import instagram as ig
    state = FakeFSMContext({"scenario_context": ""})
    message = FakeMessage(text="a reel about coffee")
    with patch.object(ig, "_ig_tov", new=AsyncMock(return_value={})), \
         patch.object(ig, "GeminiService") as G:
        G.return_value.develop_instagram_scenario = AsyncMock(
            return_value={"kind": "clarify", "question": "Audience?"})
        await ig.on_scenario_message(message, state)
    assert state.state == ig.InstagramStates.scenario_developing
```

**Step 4: Run** → FAIL.

**Step 5: Implement `bot/handlers/instagram.py`**

- `start_instagram` (`platform:instagram`): set `waiting_subtype`, send `instagram_subtype_keyboard()`.
- **Caption path** (`ig:caption`): set `collecting_caption_photos`, ask for photos; `on_caption_photo` (F.photo) appends `{"file_id": ...}` to `caption_photos`; `on_caption_photos_done` (`/done`): `_download_photos` (import from `_veo_flow`), look up IG TOV via `get_for_channel(uid, INSTAGRAM)`, call `GeminiService().caption_from_photos(paths, tov)`, show result + save card (reuse `report_card`/`linkedin_report_keyboard` or a simple message), cleanup temp files, clear state.
- **Scenario path** (`ig:scenario`): set `scenario_developing`, init `scenario_context=""`, ask for the idea. `on_scenario_message` runs the clarify-loop exactly like `_veo_flow.on_prompt_refine_instruction`: append to `scenario_context`, support `/cancel`, call `develop_instagram_scenario(idea, scenario_context, tov)`. On `clarify` → append `ASSISTANT ASKED: ...`, send question, stay. On `script` → store `scenario_script`/`scenario_caption`, set `scenario_ready`, show the script + `ig_generate_reel_keyboard()`.
- `ig:reel` (in `scenario_ready`): hand off to the shared Veo flow — `await state.update_data(description=scenario_script)` then call `_veo_flow.start_veo_flow`-equivalent but skip straight to mode selection (or pre-set `video_mode` + go to `collecting_materials`). Simplest: set `channel=INSTAGRAM`, set `VeoStates.choosing_video_mode`, send `video_mode_keyboard()`, and seed `description` so `on_materials_done` uses it. (Photos optional via the existing materials step.)
- `ig:script_done`: clear state, confirm.
- Helper `_ig_tov(user_id)` → `get_for_channel(user_id, INSTAGRAM)` profile_json or `{}`.

Register `instagram.router` in `bot/main.py`.

**Step 6: Run** new tests + full suite → PASS.

**Step 7: Commit**

```bash
git add bot/handlers/instagram.py bot/states/states.py bot/keyboards/inline.py bot/main.py tests/handlers/test_instagram.py
git commit -m "feat: Instagram content flow (photo->caption + scenario->Reel)"
```

---

## Phase F — Verification

### Task 17: Full suite + manual smoke

**Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all green, count ≥ baseline 122 + new tests.

**Step 2: Apply migration on a scratch DB and sanity-check**

Run: `python -m alembic upgrade head` then confirm `channel` column + unique index (Task 2 Step 3).

**Step 3: Manual smoke (document results, do not skip)**

Use REQUIRED SUB-SKILL: superpowers:verification-before-completion to confirm each claim with evidence:
- `/start` shows the Create-TOV button; after creating all three channels it disappears.
- Picker lists only not-yet-created channels.
- Wizard save and Apify import save for each of IG / TikTok / LinkedIn (import needs `APIFY_TOKEN`).
- `/settings` lists all three with correct status; Delete makes the channel reappear in the picker; Recreate overwrites.
- LinkedIn post-writer and TikTok video still generate (now reading their channel TOV).
- Instagram: photo→caption produces a caption from a real photo; scenario helper clarifies then yields a script; "Generate Reel" produces a video.

**Step 4: Commit any fixups, then finish**

Use REQUIRED SUB-SKILL: superpowers:finishing-a-development-branch to merge/PR `feature/per-channel-tov` into `dev`.

---

## Notes for the implementer

- **DRY:** channel slugs live only in `bot/db/channels.py`; actor field shapes live only in `bot/services/tov/config.py`. Don't duplicate.
- **YAGNI:** no multiple-TOV-per-channel, no versioning, no Reel-specific Veo prompt fork. Generic short-form copy is enough.
- **Verify Apify actor I/O:** the TikTok/LinkedIn actor input keys and result field names in `config.py` are best-guess — confirm with one real run each and adjust only that file.
- **Back-compat:** `InstagramTovService` keeps its name + error classes so existing imports/tests keep working after Task 8.
