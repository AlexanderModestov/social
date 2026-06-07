# Instagram Tone of Voice Extraction — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an Instagram profile option at the tone-of-voice entry point: user sends their public Instagram handle, bot calls the `tov_extractor` microservice, saves the rich profile, and displays it in full.

**Architecture:** A new `InstagramTovService` in the bot's service layer calls `POST /analyze` on the `tov_extractor` FastAPI app (configured via `INSTAGRAM_TOV_URL`). The handler at `action:tone_of_voice` now shows a method-choice keyboard before branching into the existing wizard or the new Instagram path. The Instagram path has no confirmation step — it auto-saves on success.

**Tech Stack:** aiogram 3, httpx (already a dep), pydantic-settings, pytest + unittest.mock

---

## Task 1: Rename `backend/` → `tov_extractor/`

**Files:**
- Rename: `backend/` → `tov_extractor/`

**Step 1: Git-rename the folder**

```bash
git mv backend tov_extractor
git commit -m "refactor: rename backend/ to tov_extractor/"
```

Expected: `git status` shows rename, no modified files inside.

---

## Task 2: Add `instagram_tov_url` to config

**Files:**
- Modify: `bot/config.py`
- Modify: `tests/test_config.py`

**Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_instagram_tov_url_defaults_to_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
    monkeypatch.delenv("INSTAGRAM_TOV_URL", raising=False)

    settings = Settings(_env_file=None)
    assert settings.instagram_tov_url is None


def test_instagram_tov_url_reads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
    monkeypatch.setenv("INSTAGRAM_TOV_URL", "http://localhost:8000")

    settings = Settings(_env_file=None)
    assert settings.instagram_tov_url == "http://localhost:8000"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_config.py::test_instagram_tov_url_defaults_to_none -v
```

Expected: `FAILED` — `Settings` has no `instagram_tov_url` field.

**Step 3: Add field to Settings**

In `bot/config.py`, add after `gcs_output_bucket`:

```python
instagram_tov_url: Optional[str] = None
```

**Step 4: Run both tests**

```bash
pytest tests/test_config.py -v
```

Expected: all PASS.

**Step 5: Commit**

```bash
git add bot/config.py tests/test_config.py
git commit -m "feat: add INSTAGRAM_TOV_URL to config"
```

---

## Task 3: Add new FSM states

**Files:**
- Modify: `bot/states/states.py`

**Step 1: Add states**

In `ToneOfVoiceStates`, add two new states before `waiting_role`:

```python
class ToneOfVoiceStates(StatesGroup):
    choosing_method = State()          # new
    waiting_instagram_handle = State() # new
    waiting_role = State()
    waiting_audience = State()
    waiting_style = State()
    waiting_examples = State()
    confirming_profile = State()
```

**Step 2: Verify import still works**

```bash
python -c "from bot.states.states import ToneOfVoiceStates; print(list(ToneOfVoiceStates))"
```

Expected: prints 7 state names without error.

**Step 3: Commit**

```bash
git add bot/states/states.py
git commit -m "feat: add choosing_method and waiting_instagram_handle FSM states"
```

---

## Task 4: Add `tov_method_keyboard`

**Files:**
- Modify: `bot/keyboards/inline.py`
- Modify: `tests/test_keyboards.py`

**Step 1: Write the failing test**

Add to `tests/test_keyboards.py`:

```python
from bot.keyboards.inline import tov_method_keyboard

def test_tov_method_keyboard_has_two_buttons():
    kb = tov_method_keyboard()
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(buttons) == 2

def test_tov_method_keyboard_callback_data():
    kb = tov_method_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "tov:wizard" in callbacks
    assert "tov:instagram" in callbacks
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_keyboards.py::test_tov_method_keyboard_has_two_buttons -v
```

Expected: `FAILED` — `cannot import name 'tov_method_keyboard'`.

**Step 3: Add keyboard**

Append to `bot/keyboards/inline.py`:

```python
def tov_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧙 Answer a few questions", callback_data="tov:wizard")],
        [InlineKeyboardButton(text="📸 Import from Instagram", callback_data="tov:instagram")],
    ])
```

**Step 4: Run all keyboard tests**

```bash
pytest tests/test_keyboards.py -v
```

Expected: all PASS.

**Step 5: Commit**

```bash
git add bot/keyboards/inline.py tests/test_keyboards.py
git commit -m "feat: add tov_method_keyboard (wizard vs instagram choice)"
```

---

## Task 5: Create `InstagramTovService`

**Files:**
- Create: `bot/services/instagram_tov_service.py`
- Create: `tests/services/test_instagram_tov_service.py`

**Step 1: Write failing tests**

Create `tests/services/test_instagram_tov_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.services.instagram_tov_service import (
    InstagramTovService,
    PrivateProfileError,
    NoPostsError,
    ServiceError,
)

FAKE_PROFILE = {
    "username": "alex",
    "posts_analyzed": 10,
    "persona_summary": "Creative",
    "archetype": "Urban nomad",
    "voice_dimensions": [],
    "language": {"primary": "English ~100%", "secondary": None, "mixing_note": None},
    "caption_patterns": [],
    "motifs": {"themes": [], "places": [], "sensory": []},
    "dos": ["Be concise"],
    "donts": ["Avoid jargon"],
    "signature_elements": {"punctuation": "...", "hashtags": "rarely", "phrases": []},
}


@pytest.mark.asyncio
async def test_analyze_returns_profile_on_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = FAKE_PROFILE
    mock_response.raise_for_status = MagicMock()

    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        svc = InstagramTovService(base_url="http://localhost:8000")
        result = await svc.analyze("alex")

    assert result["username"] == "alex"
    assert result["posts_analyzed"] == 10


@pytest.mark.asyncio
async def test_analyze_raises_private_profile_on_404():
    mock_response = MagicMock()
    mock_response.status_code = 404

    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=mock_response)
        )

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(PrivateProfileError):
            await svc.analyze("private_user")


@pytest.mark.asyncio
async def test_analyze_raises_no_posts_on_404_with_no_posts_message():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"detail": "No posts found"}

    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=mock_response)
        )

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(NoPostsError):
            await svc.analyze("empty_user")


@pytest.mark.asyncio
async def test_analyze_raises_service_error_on_502():
    mock_response = MagicMock()
    mock_response.status_code = 502

    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("bad gateway", request=MagicMock(), response=mock_response)
        )

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(ServiceError):
            await svc.analyze("alex")


@pytest.mark.asyncio
async def test_analyze_raises_service_error_on_connect_error():
    import httpx
    with patch("bot.services.instagram_tov_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        svc = InstagramTovService(base_url="http://localhost:8000")
        with pytest.raises(ServiceError):
            await svc.analyze("alex")
```

**Step 2: Run to verify failure**

```bash
pytest tests/services/test_instagram_tov_service.py -v
```

Expected: `FAILED` — module not found.

**Step 3: Create the service**

Create `bot/services/instagram_tov_service.py`:

```python
import httpx


class PrivateProfileError(Exception):
    pass


class NoPostsError(Exception):
    pass


class ServiceError(Exception):
    pass


class InstagramTovService:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def analyze(self, username: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{self._base_url}/analyze",
                    json={"username": username},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 404:
                try:
                    detail = e.response.json().get("detail", "")
                except Exception:
                    detail = ""
                if "No posts" in detail:
                    raise NoPostsError(detail) from e
                raise PrivateProfileError(str(e)) from e
            raise ServiceError(str(e)) from e
        except httpx.TransportError as e:
            raise ServiceError(str(e)) from e
```

**Step 4: Run all service tests**

```bash
pytest tests/services/test_instagram_tov_service.py -v
```

Expected: all PASS.

**Step 5: Commit**

```bash
git add bot/services/instagram_tov_service.py tests/services/test_instagram_tov_service.py
git commit -m "feat: add InstagramTovService with typed error classes"
```

---

## Task 6: Create `format_instagram_profile` helper

**Files:**
- Create: `bot/services/instagram_tov_formatter.py`
- Create: `tests/services/test_instagram_tov_formatter.py`

**Step 1: Write failing tests**

Create `tests/services/test_instagram_tov_formatter.py`:

```python
from bot.services.instagram_tov_formatter import format_instagram_profile, split_message

FULL_PROFILE = {
    "username": "alex",
    "posts_analyzed": 47,
    "persona_summary": "A reflective creator.",
    "archetype": "Urban nomad",
    "voice_dimensions": [{"name": "Warmth", "description": "Always approachable."}],
    "language": {"primary": "English ~80%", "secondary": "Russian ~20%", "mixing_note": "switches mid-post"},
    "caption_patterns": [{"name": "Observation", "frequency": "~60%", "description": "Starts with a scene.", "examples": ["Walking through..."]}],
    "motifs": {"themes": ["travel", "coffee"], "places": ["Berlin"], "sensory": ["rain smell"]},
    "dos": ["Be specific", "Use metaphors"],
    "donts": ["Avoid clichés"],
    "signature_elements": {"punctuation": "ellipses often", "hashtags": "1-2 only", "phrases": ["you know", "just"]},
}


def test_format_contains_username():
    text = format_instagram_profile(FULL_PROFILE)
    assert "@alex" in text
    assert "47 posts analyzed" in text


def test_format_contains_persona_and_archetype():
    text = format_instagram_profile(FULL_PROFILE)
    assert "reflective creator" in text
    assert "Urban nomad" in text


def test_format_contains_dos_and_donts():
    text = format_instagram_profile(FULL_PROFILE)
    assert "Be specific" in text
    assert "Avoid clichés" in text


def test_format_contains_voice_dimensions():
    text = format_instagram_profile(FULL_PROFILE)
    assert "Warmth" in text


def test_format_contains_language():
    text = format_instagram_profile(FULL_PROFILE)
    assert "English" in text
    assert "Russian" in text


def test_format_contains_motifs():
    text = format_instagram_profile(FULL_PROFILE)
    assert "travel" in text
    assert "Berlin" in text


def test_format_contains_phrases():
    text = format_instagram_profile(FULL_PROFILE)
    assert "you know" in text


def test_split_message_short_stays_as_one():
    parts = split_message("hello", max_len=4096)
    assert parts == ["hello"]


def test_split_message_long_splits_on_newline():
    chunk = "a" * 2000
    text = chunk + "\n" + chunk + "\n" + chunk
    parts = split_message(text, max_len=4096)
    assert len(parts) == 2
    for p in parts:
        assert len(p) <= 4096
```

**Step 2: Run to verify failure**

```bash
pytest tests/services/test_instagram_tov_formatter.py -v
```

Expected: `FAILED` — module not found.

**Step 3: Create the formatter**

Create `bot/services/instagram_tov_formatter.py`:

```python
def format_instagram_profile(profile: dict) -> str:
    lines = [
        f"📸 @{profile['username']} — {profile['posts_analyzed']} posts analyzed\n",
        f"👤 Persona: {profile.get('persona_summary', '')}",
        f"🎭 Archetype: {profile.get('archetype', '')}",
    ]

    dims = profile.get("voice_dimensions") or []
    if dims:
        lines.append("\n🗣 Voice dimensions:")
        for d in dims:
            lines.append(f"• {d['name']}: {d['description']}")

    lang = profile.get("language") or {}
    lang_str = lang.get("primary", "")
    if lang.get("secondary"):
        lang_str += f" / {lang['secondary']}"
    if lang.get("mixing_note"):
        lang_str += f" ({lang['mixing_note']})"
    lines.append(f"\n🌍 Language: {lang_str}")

    patterns = profile.get("caption_patterns") or []
    if patterns:
        lines.append("\n📝 Caption patterns:")
        for p in patterns:
            lines.append(f"• {p['name']} ({p.get('frequency', '')}): {p['description']}")

    motifs = profile.get("motifs") or {}
    if motifs.get("themes"):
        lines.append(f"\n🎯 Themes: {', '.join(motifs['themes'])}")
    if motifs.get("places"):
        lines.append(f"📍 Places: {', '.join(motifs['places'])}")
    if motifs.get("sensory"):
        lines.append(f"👃 Sensory: {', '.join(motifs['sensory'])}")

    dos = profile.get("dos") or []
    if dos:
        lines.append("\n✅ Do:")
        for d in dos:
            lines.append(f"• {d}")

    donts = profile.get("donts") or []
    if donts:
        lines.append("\n🚫 Don't:")
        for d in donts:
            lines.append(f"• {d}")

    sig = profile.get("signature_elements") or {}
    style_parts = [s for s in [sig.get("punctuation"), sig.get("hashtags")] if s]
    if style_parts:
        lines.append(f"\n✍️ Style: {' | '.join(style_parts)}")
    phrases = sig.get("phrases") or []
    if phrases:
        lines.append(f"💬 Phrases: {', '.join(repr(p) for p in phrases)}")

    return "\n".join(lines)


def split_message(text: str, max_len: int = 4096) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts
```

**Step 4: Run all formatter tests**

```bash
pytest tests/services/test_instagram_tov_formatter.py -v
```

Expected: all PASS.

**Step 5: Commit**

```bash
git add bot/services/instagram_tov_formatter.py tests/services/test_instagram_tov_formatter.py
git commit -m "feat: add format_instagram_profile and split_message helpers"
```

---

## Task 7: Update the tone-of-voice handler

**Files:**
- Modify: `bot/handlers/tone_of_voice.py`

**Step 1: Replace the handler**

Replace the full contents of `bot/handlers/tone_of_voice.py` with:

```python
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository
from bot.keyboards.inline import (
    style_words_keyboard,
    tone_of_voice_confirm_keyboard,
    tov_method_keyboard,
)
from bot.services.claude_service import ClaudeService
from bot.services.instagram_tov_service import (
    InstagramTovService,
    NoPostsError,
    PrivateProfileError,
    ServiceError,
)
from bot.services.instagram_tov_formatter import format_instagram_profile, split_message
from bot.states.states import ToneOfVoiceStates

router = Router()


# ── Entry point ────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "action:tone_of_voice")
async def choose_method(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ToneOfVoiceStates.choosing_method)
    await callback.message.edit_text(
        "How would you like to define your tone of voice?",
        reply_markup=tov_method_keyboard(),
    )
    await callback.answer()


# ── Wizard path ────────────────────────────────────────────────────────────────

@router.callback_query(ToneOfVoiceStates.choosing_method, F.data == "tov:wizard")
async def on_wizard_chosen(callback: CallbackQuery, state: FSMContext):
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
        if word in words:
            words = [w for w in words if w != word]
        else:
            words = words + [word]
        await state.update_data(style_words=words)
        await callback.message.edit_reply_markup(reply_markup=style_words_keyboard(words))
    await callback.answer()


@router.message(ToneOfVoiceStates.waiting_examples, F.text != "/done")
async def on_example(message: Message, state: FSMContext):
    data = await state.get_data()
    examples = data.get("examples", [])
    examples.append(message.text)
    await state.update_data(examples=examples)
    count = len(examples)
    await message.answer(f"Got it ({count} example{'s' if count > 1 else ''} so far). Send more or type /done.")


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
            name=f"Profile {data.get('role', '')[:30]}",
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
    try:
        profile = await service.generate_tone_of_voice(
            role=data["role"],
            audience=data["audience"],
            style_words=data["style_words"],
            examples=data["examples"],
        )
    except Exception as e:
        await callback.message.edit_text(
            f"Error regenerating profile: {e}. Please try again.",
            reply_markup=tone_of_voice_confirm_keyboard(),
        )
        await callback.answer()
        return
    await state.update_data(generated_profile=profile)
    profile_text = (
        f"*Your tone of voice profile:*\n\n"
        f"*Voice:* {profile.get('voice_summary', '')}\n"
        f"*Style:* {', '.join(profile.get('tone_words', []))}\n"
        f"*Always:* {'; '.join(profile.get('always', []))}\n"
        f"*Avoid:* {'; '.join(profile.get('avoid', []))}\n"
        f"*Audience:* {profile.get('audience', '')}"
    )
    await callback.message.edit_text(profile_text, parse_mode="Markdown", reply_markup=tone_of_voice_confirm_keyboard())
    await callback.answer()


# ── Instagram path ─────────────────────────────────────────────────────────────

@router.callback_query(ToneOfVoiceStates.choosing_method, F.data == "tov:instagram")
async def on_instagram_chosen(callback: CallbackQuery, state: FSMContext):
    if not settings.instagram_tov_url:
        await callback.message.edit_text(
            "Instagram extraction is not configured. Please start the wizard instead.",
            reply_markup=tov_method_keyboard(),
        )
        await callback.answer()
        return
    await state.set_state(ToneOfVoiceStates.waiting_instagram_handle)
    await callback.message.edit_text(
        "Send your Instagram username or profile URL.\n\n"
        "Examples: @alex  or  https://instagram.com/alex"
    )
    await callback.answer()


@router.message(ToneOfVoiceStates.waiting_instagram_handle)
async def on_instagram_handle(message: Message, state: FSMContext):
    await message.answer("Analyzing your Instagram profile… this takes ~1–2 minutes ⏳")

    svc = InstagramTovService(base_url=settings.instagram_tov_url)
    try:
        profile = await svc.analyze(message.text.strip())
    except PrivateProfileError:
        await state.clear()
        await message.answer(
            "Profile is private or doesn't exist.\n"
            "Send /start to try again or choose the wizard instead."
        )
        return
    except NoPostsError:
        await state.clear()
        await message.answer(
            "No posts with captions were found on that profile.\n"
            "Send /start to try again or choose the wizard instead."
        )
        return
    except ServiceError:
        await state.clear()
        await message.answer(
            "The extraction service is unavailable right now.\n"
            "Send /start to try again or choose the wizard instead."
        )
        return

    async with async_session_factory() as session:
        repo = ToneOfVoiceRepository(session)
        await repo.create(
            user_id=message.from_user.id,
            name=f"Instagram @{profile.get('username', '')}",
            profile_json=profile,
        )
        await session.commit()

    await state.clear()

    formatted = format_instagram_profile(profile)
    for part in split_message(formatted):
        await message.answer(part)
```

**Step 2: Run the full test suite**

```bash
pytest -v
```

Expected: all existing tests still PASS (handler is not unit-tested directly; integration covered by the service/formatter tests).

**Step 3: Commit**

```bash
git add bot/handlers/tone_of_voice.py
git commit -m "feat: add Instagram tone-of-voice path to handler (method choice → auto-save)"
```

---

## Task 8: Add `INSTAGRAM_TOV_URL` to `.env.example` / docs

**Files:**
- Modify: `.env.example` (if it exists) or note in README

**Step 1: Check for .env.example**

```bash
ls .env* 2>/dev/null || echo "none"
```

**Step 2a: If `.env.example` exists**, add:

```
INSTAGRAM_TOV_URL=http://localhost:8000
```

**Step 2b: If it doesn't exist**, skip — the config field has a `None` default and the handler guards against it.

**Step 3: Commit if changed**

```bash
git add .env.example
git commit -m "chore: document INSTAGRAM_TOV_URL in .env.example"
```

---

## Task 9: Final check

**Step 1: Run full test suite**

```bash
pytest -v
```

Expected: all PASS, no warnings about missing imports.

**Step 2: Verify module imports are clean**

```bash
python -c "
from bot.services.instagram_tov_service import InstagramTovService
from bot.services.instagram_tov_formatter import format_instagram_profile, split_message
from bot.keyboards.inline import tov_method_keyboard
from bot.states.states import ToneOfVoiceStates
print('all imports OK')
"
```

Expected: `all imports OK`
