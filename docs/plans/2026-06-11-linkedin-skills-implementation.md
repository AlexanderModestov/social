# LinkedIn Skills Port — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Port all 10 skills from `sergebulaev/linkedin-skills` into the Telegram bot as on-demand, request/response flows behind a LinkedIn submenu, with manual-publish now and Publora-ready tiering.

**Architecture:** Vendor the repo's skill *content* (`SKILL.md` + `references/*.md`) and pure-Python *libs* (`url_parser`, `apify_client`, `publora_client`, `backend_selector`) into the bot. A `SkillPromptLoader` assembles per-skill system prompts (global voice rules + user tone-of-voice + SKILL.md + inlined references); a `LinkedInSkillService` calls Claude. aiogram handlers (one router per skill) drive each flow. Reads use Apify when `apify_token` is set, else paste-fallback. Publish uses `backend_selector` (manual copy-paste now).

**Tech Stack:** Python 3.10, aiogram 3, SQLAlchemy async, anthropic SDK (`claude-sonnet-4-6`), pytest + pytest-asyncio, `requests` (vendored libs, wrapped in `asyncio.to_thread`).

**Design doc:** `docs/plans/2026-06-11-linkedin-skills-design.md`

---

## Conventions for every task

- **TDD**: write the failing test first, watch it fail, implement minimally, watch it pass, commit. REQUIRED SUB-SKILL: superpowers:test-driven-development.
- Run a single test: `pytest <path>::<test> -v`. Run a file: `pytest <path> -v`.
- All Apify/Publora/Anthropic calls are **mocked** in tests — no live network.
- Commit after each green step. Keep commits small.
- The upstream repo is cloned fresh into a temp dir for copy steps:
  ```bash
  git clone --depth 1 https://github.com/sergebulaev/linkedin-skills.git /tmp/lis
  ```
  (On Windows PowerShell use `$env:TEMP\lis`. Paths below use `/tmp/lis`.)

---

# PHASE 1 — Foundation

## Task 1: Vendor the pure-Python libs

**Files:**
- Create: `bot/services/linkedin/__init__.py`
- Create: `bot/services/linkedin/url_parser.py` (copy)
- Create: `bot/services/linkedin/apify_client.py` (copy)
- Create: `bot/services/linkedin/publora_client.py` (copy)
- Create: `bot/services/linkedin/backend_selector.py` (copy)
- Test: `tests/services/linkedin/test_url_parser.py`

**Step 1: Copy the libs verbatim**

```bash
mkdir -p bot/services/linkedin
cp /tmp/lis/lib/url_parser.py        bot/services/linkedin/url_parser.py
cp /tmp/lis/lib/apify_client.py      bot/services/linkedin/apify_client.py
cp /tmp/lis/lib/publora_client.py    bot/services/linkedin/publora_client.py
cp /tmp/lis/lib/backend_selector.py  bot/services/linkedin/backend_selector.py
```

Fix the relative import in `backend_selector.py`: it does
`from .publora_client import PubloraClient` and `from .apify_client import ...`
— these already work as a package since all four files live in
`bot/services/linkedin/`. Create `bot/services/linkedin/__init__.py`:

```python
from .url_parser import parse_linkedin_url, build_parent_comment_urn
from .backend_selector import active_backend, publish, fetch_post, manual_mode_message

__all__ = [
    "parse_linkedin_url",
    "build_parent_comment_urn",
    "active_backend",
    "publish",
    "fetch_post",
    "manual_mode_message",
]
```

**Step 2: Write the failing test** (`tests/services/linkedin/test_url_parser.py`)

```python
import pytest
from bot.services.linkedin.url_parser import parse_linkedin_url, build_parent_comment_urn


def test_activity_post_url():
    p = parse_linkedin_url(
        "https://www.linkedin.com/posts/jane_activity-7448808898326654978-iW20"
    )
    assert p["post_urn"] == "urn:li:activity:7448808898326654978"
    assert p["post_activity_id"] == "7448808898326654978"
    assert p["url_type"] == "post"


def test_share_post_url():
    p = parse_linkedin_url(
        "https://www.linkedin.com/posts/ivan_one-broker-share-7449499107418669056-ZYt7"
    )
    assert p["post_urn"] == "urn:li:share:7449499107418669056"
    assert p["url_type"] == "post"


def test_comment_url_extracts_post_and_comment():
    p = parse_linkedin_url(
        "https://www.linkedin.com/feed/update/urn:li:activity:7448387840113184768"
        "?commentUrn=urn%3Ali%3Acomment%3A%28activity%3A7448387840113184768"
        "%2C7449095071892672512%29"
    )
    assert p["url_type"] == "comment"
    assert p["post_urn"] == "urn:li:activity:7448387840113184768"
    assert p["comment_id"] == "7449095071892672512"


def test_unknown_url():
    assert parse_linkedin_url("https://example.com/foo")["url_type"] == "unknown"


def test_build_parent_comment_urn():
    urn = build_parent_comment_urn("urn:li:activity:123", "456")
    assert urn == "urn:li:comment:(urn:li:activity:123,456)"
```

Also create empty `tests/services/linkedin/__init__.py` if your test layout needs it (check existing `tests/services/`).

**Step 3: Run to verify** — `pytest tests/services/linkedin/test_url_parser.py -v` → PASS (the vendored parser already implements this).

**Step 4: Commit**

```bash
git add bot/services/linkedin tests/services/linkedin
git commit -m "feat: vendor linkedin-skills libs (url_parser, apify, publora, backend_selector)"
```

---

## Task 2: Vendor skill content (SKILL.md + references)

**Files:**
- Create: `skills/linkedin/references/*.md` (shared references)
- Create: `skills/linkedin/<skill>/SKILL.md` (+ each skill's `references/`)
- Create: `skills/linkedin/root_voice_rules.md` (extracted global voice rules)

**Step 1: Copy skill trees + shared references**

```bash
cp -r /tmp/lis/skills/*        skills/linkedin/
cp -r /tmp/lis/references       skills/linkedin/references
```

This yields `skills/linkedin/linkedin-post-writer/SKILL.md`, etc., plus
`skills/linkedin/references/{hook-formulas,voice-rules,algorithm-heuristics,engagement-metrics-taxonomy,industry-benchmarks}.md`.

**Step 2: Resolve the stale "this file moved" stubs**

Two files are stubs pointing at the root references (verified during design):
`skills/linkedin/linkedin-post-writer/references/hook-formulas.md` says "moved to
root-level references". Replace each stub with the real content:

```bash
cp /tmp/lis/references/hook-formulas.md \
   skills/linkedin/linkedin-post-writer/references/hook-formulas.md
```

Grep for any other stubs and resolve the same way:
```bash
grep -rl "This file moved" skills/linkedin/
```

**Step 3: Extract the global voice rules**

The 6 global voice rules live in the repo root `SKILL.md` §"Voice rules" and the
README. Create `skills/linkedin/root_voice_rules.md` with exactly those 6 rules
(copy the README "Voice rules" section body verbatim):

```markdown
# Global voice rules (apply to every skill)

1. No em dashes. Biggest AI tell in 2026.
2. Capitalize names. Always. Lowercase reads as disrespectful.
3. No AI vocabulary: "leverage", "fundamentally", "streamline", "harness", "delve", "unlock", "foster".
4. Specific numbers beat adjectives. "$14,200" beats "significant savings".
5. One sharp insight per comment beats three vague ones.
6. 200-350 chars for comments, 900-1,300 chars for posts.
```

**Step 4: Commit**

```bash
git add skills/linkedin
git commit -m "feat: vendor linkedin-skills content (SKILL.md + references)"
```

---

## Task 3: `SkillPromptLoader`

**Files:**
- Create: `bot/services/linkedin/prompt_loader.py`
- Test: `tests/services/linkedin/test_prompt_loader.py`

Maps a short skill key (`"post-writer"`) to its vendored dir
(`skills/linkedin/linkedin-post-writer`). Reads `SKILL.md`, inlines every
referenced `*.md` (both `references/x.md` and `../../references/x.md` link
forms), prepends global voice rules + the user's tone-of-voice JSON, and caches
the static portion per skill.

**Step 1: Write the failing test**

```python
import json
from bot.services.linkedin.prompt_loader import SkillPromptLoader


def test_loads_skill_and_inlines_references():
    loader = SkillPromptLoader()
    prompt = loader.build("post-writer", tov={"role": "founder"})
    # SKILL.md body present
    assert "LinkedIn Post Writer" in prompt
    # a referenced file got inlined (hook formulas table)
    assert "Platform Risk Anaphora" in prompt
    # global voice rules prepended
    assert "No em dashes" in prompt
    # user ToV injected
    assert '"role": "founder"' in prompt or "founder" in prompt


def test_no_unresolved_reference_links_remain():
    loader = SkillPromptLoader()
    prompt = loader.build("post-writer", tov={})
    assert "../../references/" not in prompt
    assert "This file moved" not in prompt


def test_unknown_skill_raises():
    import pytest
    with pytest.raises(KeyError):
        SkillPromptLoader().build("does-not-exist", tov={})
```

**Step 2: Run to verify it fails** — `ModuleNotFoundError`.

**Step 3: Implement** (`bot/services/linkedin/prompt_loader.py`)

```python
import json
import re
from functools import lru_cache
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[3] / "skills" / "linkedin"

# short key -> vendored directory name
SKILL_DIRS = {
    "post-writer": "linkedin-post-writer",
    "comment-drafter": "linkedin-comment-drafter",
    "reply-handler": "linkedin-reply-handler",
    "humanizer": "linkedin-humanizer",
    "post-audit": "linkedin-humanizer",          # audit is a humanizer mode
    "hook-extractor": "linkedin-hook-extractor",
    "engagement-monitor": "linkedin-engager-analytics",
    "profile-optimizer": "linkedin-profile-optimizer",
    "content-planner": "linkedin-content-planner",
    "employee-advocacy": "linkedin-employee-advocacy",
}

_REF_LINK_RE = re.compile(r"`?((?:\.\./)*references/[\w\-./]+\.md)`?")


class SkillPromptLoader:
    def __init__(self, root: Path = SKILLS_ROOT):
        self.root = root

    @lru_cache(maxsize=32)
    def _static_prompt(self, skill: str) -> str:
        if skill not in SKILL_DIRS:
            raise KeyError(f"unknown skill: {skill}")
        skill_dir = self.root / SKILL_DIRS[skill]
        skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        voice = (self.root / "root_voice_rules.md").read_text(encoding="utf-8")

        inlined = []
        for rel in dict.fromkeys(_REF_LINK_RE.findall(skill_md)):  # de-dupe, keep order
            path = self._resolve_ref(skill_dir, rel)
            if path and path.exists():
                body = path.read_text(encoding="utf-8")
                inlined.append(f"\n\n# Reference: {path.name}\n\n{body}")

        return f"{voice}\n\n# Skill instructions\n\n{skill_md}" + "".join(inlined)

    def _resolve_ref(self, skill_dir: Path, rel: str) -> Path | None:
        # try skill-local first, then root-level references
        for base in (skill_dir, self.root):
            candidate = (base / rel).resolve()
            if candidate.exists():
                return candidate
        # bare references/x.md under root
        name = rel.split("/")[-1]
        candidate = self.root / "references" / name
        return candidate if candidate.exists() else None

    def build(self, skill: str, tov: dict) -> str:
        static = self._static_prompt(skill)
        tov_block = json.dumps(tov, indent=2) if tov else "(none provided)"
        return f"{static}\n\n# User tone-of-voice profile\n\n{tov_block}"
```

**Step 4: Run to verify** — `pytest tests/services/linkedin/test_prompt_loader.py -v` → PASS. If `test_no_unresolved_reference_links_remain` fails, it means a stub wasn't resolved in Task 2 — go fix the stub, not the test.

**Step 5: Commit**

```bash
git add bot/services/linkedin/prompt_loader.py tests/services/linkedin/test_prompt_loader.py
git commit -m "feat: SkillPromptLoader assembles per-skill system prompts"
```

---

## Task 4: `LinkedInSkillService`

**Files:**
- Create: `bot/services/linkedin/skill_service.py`
- Test: `tests/services/linkedin/test_skill_service.py`

**Step 1: Write the failing test** (mock the Anthropic client)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.services.linkedin.skill_service import LinkedInSkillService


@pytest.mark.asyncio
async def test_run_builds_prompt_and_returns_text(monkeypatch):
    svc = LinkedInSkillService()

    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="DRAFTED POST")]
    svc.client.messages.create = AsyncMock(return_value=fake_msg)

    out = await svc.run(
        skill="post-writer",
        user_inputs={"topic": "AI agencies", "notes": "be bold"},
        tov={"role": "founder"},
    )
    assert out == "DRAFTED POST"

    kwargs = svc.client.messages.create.call_args.kwargs
    assert "LinkedIn Post Writer" in kwargs["system"]      # skill prompt used
    assert "AI agencies" in kwargs["messages"][0]["content"]  # inputs passed
    assert kwargs["model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_run_includes_previous_and_feedback():
    svc = LinkedInSkillService()
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="REVISED")]
    svc.client.messages.create = AsyncMock(return_value=fake_msg)

    await svc.run(
        skill="post-writer",
        user_inputs={"topic": "x"},
        tov={},
        previous="OLD DRAFT",
        feedback="make it shorter",
    )
    user_content = svc.client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "OLD DRAFT" in user_content
    assert "make it shorter" in user_content
```

**Step 2: Run to verify it fails** — `ModuleNotFoundError`.

**Step 3: Implement** (`bot/services/linkedin/skill_service.py`)

```python
import json
import anthropic
from bot.config import settings
from bot.services.linkedin.prompt_loader import SkillPromptLoader

# per-skill output budgets
MAX_TOKENS = {
    "content-planner": 4096,
    "employee-advocacy": 4096,
    "profile-optimizer": 3072,
}
DEFAULT_MAX_TOKENS = 2048


class LinkedInSkillService:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.loader = SkillPromptLoader()

    async def run(
        self,
        skill: str,
        user_inputs: dict,
        tov: dict,
        previous: str | None = None,
        feedback: str | None = None,
    ) -> str:
        system = self.loader.build(skill, tov)

        parts = []
        for key, value in user_inputs.items():
            if value:
                label = key.replace("_", " ").upper()
                rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
                parts.append(f"{label}:\n{rendered}")
        if previous and feedback:
            parts.append(f"PREVIOUS OUTPUT:\n{previous}\n\nFEEDBACK:\n{feedback}")

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=MAX_TOKENS.get(skill, DEFAULT_MAX_TOKENS),
            system=system,
            messages=[{"role": "user", "content": "\n\n".join(parts)}],
        )
        return response.content[0].text
```

**Step 4: Run to verify** — `pytest tests/services/linkedin/test_skill_service.py -v` → PASS.

**Step 5: Commit**

```bash
git add bot/services/linkedin/skill_service.py tests/services/linkedin/test_skill_service.py
git commit -m "feat: LinkedInSkillService runs any vendored skill via Claude"
```

---

## Task 5: Config — add Publora settings (manual-mode default)

**Files:**
- Modify: `bot/config.py:11-21`
- Modify: `requirements.txt`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from bot.config import settings


def test_publora_settings_optional_and_unset_by_default():
    assert settings.publora_api_key is None
    assert settings.linkedin_platform_id is None
```

**Step 2: Run to verify it fails** — `AttributeError`.

**Step 3: Implement** — add two fields to `Settings` (after `apify_token`):

```python
    publora_api_key: Optional[str] = None
    linkedin_platform_id: Optional[str] = None
```

Add `requests` to `requirements.txt` (one line) if not already present:
```bash
grep -qi '^requests' requirements.txt || echo 'requests' >> requirements.txt
```

> Note: `backend_selector.active_backend()` reads `PUBLORA_API_KEY` /
> `LINKEDIN_PLATFORM_ID` from **os env**. Unset → manual mode. The Settings
> fields exist so a future task can `os.environ`-export them; for now leaving
> them unset is correct (manual publish).

**Step 4: Run to verify** — `pytest tests/test_config.py -v` → PASS.

**Step 5: Commit**

```bash
git add bot/config.py requirements.txt tests/test_config.py
git commit -m "feat: add optional Publora settings (manual mode default)"
```

---

## Task 6: Convert `handlers/linkedin.py` into a package + submenu

**Files:**
- Create: `bot/handlers/linkedin/__init__.py`
- Create: `bot/handlers/linkedin/menu.py`
- Create: `bot/keyboards/inline.py` additions (LinkedIn submenu keyboard)
- Move: `bot/handlers/linkedin.py` → `bot/handlers/linkedin/post_writer.py` (Task 8 refactors it)
- Modify: `bot/main.py:16,34-37`
- Test: `tests/test_keyboards.py`

**Step 1: Write the failing keyboard test** (append to `tests/test_keyboards.py`)

```python
from bot.keyboards.inline import linkedin_menu_keyboard


def test_linkedin_menu_has_all_skills():
    kb = linkedin_menu_keyboard()
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    for skill in [
        "li:post-writer", "li:comment-drafter", "li:reply-handler",
        "li:humanizer", "li:post-audit", "li:hook-extractor",
        "li:engagement-monitor", "li:profile-optimizer",
        "li:content-planner", "li:employee-advocacy",
    ]:
        assert skill in data
```

**Step 2: Run to verify it fails.**

**Step 3: Implement the keyboard** (`bot/keyboards/inline.py`)

```python
def linkedin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Write post", callback_data="li:post-writer")],
        [InlineKeyboardButton(text="💬 Draft comment", callback_data="li:comment-drafter"),
         InlineKeyboardButton(text="↩️ Draft reply", callback_data="li:reply-handler")],
        [InlineKeyboardButton(text="🧹 Humanize", callback_data="li:humanizer"),
         InlineKeyboardButton(text="🔎 Audit", callback_data="li:post-audit")],
        [InlineKeyboardButton(text="🪝 Hook extractor", callback_data="li:hook-extractor"),
         InlineKeyboardButton(text="📊 Engagement", callback_data="li:engagement-monitor")],
        [InlineKeyboardButton(text="👤 Profile", callback_data="li:profile-optimizer")],
        [InlineKeyboardButton(text="🗓 7-day plan", callback_data="li:content-planner"),
         InlineKeyboardButton(text="🤝 Advocacy", callback_data="li:employee-advocacy")],
    ])
```

**Step 4: Implement the package + menu router**

- `mkdir bot/handlers/linkedin && git mv bot/handlers/linkedin.py bot/handlers/linkedin/post_writer.py`
- `bot/handlers/linkedin/menu.py`:

```python
from aiogram import F, Router
from aiogram.types import CallbackQuery
from bot.keyboards.inline import linkedin_menu_keyboard

router = Router()


@router.callback_query(F.data == "platform:linkedin")
async def show_linkedin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Choose a LinkedIn skill:", reply_markup=linkedin_menu_keyboard()
    )
    await callback.answer()
```

- `bot/handlers/linkedin/__init__.py` — re-export a list of routers:

```python
from . import menu, post_writer  # add more as phases land

routers = [menu.router, post_writer.router]
```

- `bot/main.py`: replace `from bot.handlers import ... linkedin ...` and the
  single `dp.include_router(linkedin.router)` with:

```python
from bot.handlers import start, tone_of_voice, tiktok
from bot.handlers import linkedin as linkedin_pkg
...
for r in linkedin_pkg.routers:
    dp.include_router(r)
```

> The old `post_writer.py` still owns `@router.callback_query(... "platform:linkedin")`.
> Remove that handler from `post_writer.py` (the menu now owns it); Task 8 makes
> post_writer start on `li:post-writer` instead.

**Step 5: Run** — `pytest tests/test_keyboards.py -v` → PASS. Also `pytest -q` to confirm nothing else broke from the move.

**Step 6: Commit**

```bash
git add bot/handlers/linkedin bot/keyboards/inline.py bot/main.py tests/test_keyboards.py
git commit -m "feat: LinkedIn submenu + handlers package"
```

---

## Task 7: Shared handler helpers

**Files:**
- Create: `bot/handlers/linkedin/_shared.py`
- Test: `tests/handlers/test_linkedin_shared.py`

Provides `resolve_source`, `approval_card`, `report_card`, and a `run_skill`
convenience that loads the user's active ToV and calls `LinkedInSkillService`.

**Step 1: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from bot.handlers.linkedin import _shared


@pytest.mark.asyncio
async def test_resolve_source_uses_apify_when_url_and_token(monkeypatch):
    monkeypatch.setattr(_shared.settings, "apify_token", "tok", raising=False)
    with patch.object(_shared, "fetch_post", return_value={"text": "POST BODY"}) as fp:
        text, used = await _shared.resolve_source(
            "https://www.linkedin.com/posts/x-activity-7448808898326654978-AA"
        )
    assert "POST BODY" in text
    assert used == "apify"
    fp.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_source_asks_paste_when_no_url():
    text, used = await _shared.resolve_source("just some pasted text")
    assert text == "just some pasted text"
    assert used == "paste"
```

**Step 2: Run to verify it fails.**

**Step 3: Implement** (`bot/handlers/linkedin/_shared.py`)

```python
import asyncio
from aiogram.types import Message, CallbackQuery
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db.repository import ToneOfVoiceRepository, PostHistoryRepository
from bot.keyboards.inline import post_actions_keyboard
from bot.services.linkedin import parse_linkedin_url, fetch_post
from bot.services.linkedin.skill_service import LinkedInSkillService

_service = LinkedInSkillService()


async def resolve_source(text: str) -> tuple[str, str]:
    """Return (content, source) where source is 'apify' | 'paste' | 'empty'."""
    parsed = parse_linkedin_url(text or "")
    is_url = parsed["url_type"] != "unknown"
    if is_url and settings.apify_token:
        post = await asyncio.to_thread(fetch_post, text)
        if post and post.get("text"):
            return post["text"], "apify"
    if is_url:
        # URL but no Apify/empty — caller should ask user to paste the body
        return "", "needs_paste"
    if text and text.strip():
        return text, "paste"
    return "", "empty"


async def get_active_tov(user_id: int) -> dict:
    async with async_session_factory() as session:
        tov = await ToneOfVoiceRepository(session).get_active(user_id)
    return tov.profile_json if tov else {}


async def run_skill(skill, user_inputs, user_id, previous=None, feedback=None) -> str:
    tov = await get_active_tov(user_id)
    return await _service.run(skill, user_inputs, tov, previous=previous, feedback=feedback)


def approval_card(draft: str) -> dict:
    chars = len(draft)
    body = (
        f"{draft}\n\n"
        f"— {chars} chars · best window: Tue/Wed/Thu 7:30–9:00 AM"
    )
    return {"text": body, "reply_markup": post_actions_keyboard()}


async def save_history(user_id, skill, inputs, output):
    async with async_session_factory() as session:
        await PostHistoryRepository(session).create(
            user_id=user_id, platform="linkedin", format=skill,
            input_data=inputs, output_data={"output": output},
        )
        await session.commit()
```

**Step 4: Run** — `pytest tests/handlers/test_linkedin_shared.py -v` → PASS.

**Step 5: Commit**

```bash
git add bot/handlers/linkedin/_shared.py tests/handlers/test_linkedin_shared.py
git commit -m "feat: shared linkedin handler helpers (resolve_source, run_skill, cards)"
```

---

## Task 8: Refactor Post Writer onto the new service

**Files:**
- Modify: `bot/handlers/linkedin/post_writer.py`
- Modify: `bot/services/claude_service.py:46-69` (delegate)
- Modify: `bot/states/states.py:12-14`
- Test: `tests/handlers/test_post_writer.py`

**Goal:** Post Writer starts on `li:post-writer`, keeps the collect-links/notes-
then-`/done` UX, but generation goes through `run_skill("post-writer", ...)`.
`ClaudeService.generate_linkedin_post` delegates to the new service so there's
one code path.

**Step 1: Write the failing test** — assert the start handler triggers on
`li:post-writer` and that `/done` calls `run_skill` with assembled inputs (mock
`_shared.run_skill` and `ScraperService`). Model the test on the existing
handler tests.

**Step 2: Run to verify it fails.**

**Step 3: Implement**

- In `post_writer.py`: change the start trigger from `c.data == "platform:linkedin"`
  to `c.data == "li:post-writer"`. In `on_done`/`on_regenerate`/`on_edit_feedback`,
  replace the direct `ClaudeService().generate_linkedin_post(...)` call with:

```python
from bot.handlers.linkedin._shared import resolve_source, run_skill, approval_card

scraped = []
for link in data.get("links", []):
    body, _ = await resolve_source(link)
    if body:
        scraped.append(body)

post = await run_skill(
    "post-writer",
    user_inputs={
        "notes": "\n\n".join(data.get("notes", [])),
        "reference_articles": "\n\n---\n\n".join(scraped),
    },
    user_id=message.from_user.id,
)
card = approval_card(post)
await message.answer(card["text"], reply_markup=card["reply_markup"])
```

- In `claude_service.py`, make `generate_linkedin_post` delegate:

```python
async def generate_linkedin_post(self, notes, scraped_content, tone_profile,
                                 previous_post=None, feedback=None) -> str:
    from bot.services.linkedin.skill_service import LinkedInSkillService
    return await LinkedInSkillService().run(
        "post-writer",
        user_inputs={"notes": notes,
                     "reference_articles": "\n\n---\n\n".join(scraped_content)},
        tov=tone_profile, previous=previous_post, feedback=feedback,
    )
```

(Keep the method for backward compat with existing tests; update
`tests/services/test_claude_service.py` to mock the delegated service.)

**Step 4: Run** — `pytest tests/handlers/test_post_writer.py tests/services/test_claude_service.py -v` → PASS.

**Step 5: Commit**

```bash
git add bot/handlers/linkedin/post_writer.py bot/services/claude_service.py bot/states/states.py tests
git commit -m "refactor: Post Writer uses LinkedInSkillService + new submenu entry"
```

---

## Task 9: Publish action (manual mode)

**Files:**
- Modify: `bot/keyboards/inline.py:25-30` (add Publish button)
- Modify: `bot/handlers/linkedin/post_writer.py` (handle `post:publish`)
- Test: `tests/handlers/test_publish.py`

**Step 1: Write the failing test** — on `post:publish`, with no Publora env set,
`backend_selector.publish(kind="post", ...)` returns `{"mode": "manual", "message": ...}`
and the handler sends that copy-paste message. Mock `publish`.

**Step 2–4:** Add `InlineKeyboardButton(text="🚀 Publish", callback_data="post:publish")`
to `post_actions_keyboard`. Handler:

```python
from bot.services.linkedin import publish

@router.callback_query(LinkedInStates.editing, F.data == "post:publish")
async def on_publish(callback, state):
    data = await state.get_data()
    result = await asyncio.to_thread(
        publish, "post", data["generated_post"],
        "https://www.linkedin.com/post/new/",
    )
    await callback.message.answer(result["message"])  # manual-mode copy-paste block
    await callback.answer()
```

Verify PASS, commit:
```bash
git commit -am "feat: manual-mode Publish action via backend_selector"
```

---

# PHASE 2 — Improve skills (paste-in, no Apify)

> These reuse `run_skill` + a single `waiting_input` state each. Per skill: add
> a `StatesGroup`, a router file, register it in `handlers/linkedin/__init__.py`.

## Task 10: Humanizer

**Files:**
- Create: `bot/handlers/linkedin/humanizer.py`
- Modify: `bot/states/states.py`, `bot/handlers/linkedin/__init__.py`, `bot/keyboards/inline.py` (mode toggle)
- Test: `tests/handlers/test_humanizer.py`

**Flow:** `li:humanizer` → "Paste the text to humanize." → user pastes →
`run_skill("humanizer", {"draft": text, "mode": mode})` → show result + a
**mode toggle** keyboard (strict/aesthetic/forensic) that re-runs on the same
input, plus **Save**.

**Step 1 (test):** start handler triggers on `li:humanizer`; pasting text in
`HumanizerStates.waiting_input` calls `run_skill("humanizer", ...)` with the
pasted draft and default mode `"strict"`. Mock `run_skill`.

**Steps 2–4:** implement per the template. `States`: `class HumanizerStates(StatesGroup): waiting_input = State()`.
Mode keyboard callbacks `hmz:strict|aesthetic|forensic` re-run with stored input.

**Step 5 (commit):** `git commit -m "feat: Humanizer skill (strict/aesthetic/forensic)"`

## Task 11: Post Audit

**Files:** `bot/handlers/linkedin/audit.py`, states, `__init__.py`, test.

**Flow:** `li:post-audit` → "Paste the draft to audit." → `run_skill("post-audit",
{"draft": text})` → show the scored report (no rewrite) + **Save**. Note:
`post-audit` maps to the humanizer dir's audit sub-skill in `SKILL_DIRS`; the
audit-checklist references are inlined by the loader. Verify the loader inlines
`audit-checklist.md` (add an assertion to the prompt-loader test if needed).

**Commit:** `git commit -m "feat: Post Audit skill (algorithm + AI-detection report)"`

---

# PHASE 3 — Read-side skills (share `resolve_source`)

> Per skill: `waiting_input` state; on input, call `resolve_source`. If it
> returns `("", "needs_paste")`, reply "Couldn't fetch — paste the text" and stay
> in state to capture the pasted body. Then `run_skill`.

## Task 12: Comment Drafter
**Files:** `bot/handlers/linkedin/comment.py`, states, `__init__.py`, test.
**Flow:** `li:comment-drafter` → "Send the post URL (or paste its text)." →
`resolve_source` → `run_skill("comment-drafter", {"post": body})` → approval card
(comment) + Publish. Publish uses `parse_linkedin_url` to get `post_urn`, then
`publish("comment", draft, url, post_urn=..., platform_id=settings.linkedin_platform_id)`
→ manual mode message now.
**Commit:** `feat: Comment Drafter skill`

## Task 13: Reply Handler
**Files:** `bot/handlers/linkedin/reply.py`, states, `__init__.py`, test.
**Flow:** `li:reply-handler` → "Send the comment URL (or paste the thread)." →
`parse_linkedin_url` extracts `post_urn` + `comment_id`; if Apify available,
`apify_client.fetch_post_comments` for thread context. `run_skill("reply-handler",
{"thread": ...})`. Publish builds `parent_comment` via `build_parent_comment_urn`
(top-level comment URN — 2-level flattening). Manual mode now.
**Commit:** `feat: Reply Handler skill (2-level thread flattening)`

## Task 14: Hook Extractor
**Files:** `bot/handlers/linkedin/hook_extractor.py`, states, `__init__.py`, test.
**Flow:** `li:hook-extractor` → "Send a viral post URL (or paste it)." →
`resolve_source` → `run_skill("hook-extractor", {"post": body})` → report
(formula + blank template) + **Save**.
**Commit:** `feat: Hook Extractor skill`

## Task 15: Engagement Monitor (on-demand)
**Files:** `bot/handlers/linkedin/engagement.py`, states, `__init__.py`, test.
**Flow:** `li:engagement-monitor` → "Send a post URL." → requires Apify;
`apify_client.fetch_post_engagers(post_url=...)` (wrap in `to_thread`). If no
`apify_token`, reply "This skill needs an Apify token configured." →
`run_skill("engagement-monitor", {"engagers": [...]})` → ICP-grouped report +
suggested replies. **No background tracking.**
**Commit:** `feat: Engagement Monitor skill (on-demand engager analysis)`

## Task 16: Profile Optimizer
**Files:** `bot/handlers/linkedin/profile.py`, states, `__init__.py`, test.
**Flow:** `li:profile-optimizer` → "Send your profile URL, or paste your
headline + About + Experience." → `resolve_source` (profile URLs usually need
paste; that's fine) → `run_skill("profile-optimizer", {"profile": text})` →
rewritten sections + **Save**.
**Commit:** `feat: Profile Optimizer skill`

---

# PHASE 4 — Planning skills (pure generation)

## Task 17: Content Planner
**Files:** `bot/handlers/linkedin/planner.py`, states, `__init__.py`, test.
**Flow:** `li:content-planner` → collect role + audience (two short prompts) →
`run_skill("content-planner", {"role": r, "audience": a})` (max_tokens 4096) →
7-day plan + **Save**.
**Commit:** `feat: Content Planner skill (7-day plan)`

## Task 18: Employee Advocacy
**Files:** `bot/handlers/linkedin/advocacy.py`, states, `__init__.py`, test.
**Flow:** `li:employee-advocacy` → collect team context (one free-text prompt) →
`run_skill("employee-advocacy", {"context": text})` (max_tokens 4096) → 14-day
program + **Save**.
**Commit:** `feat: Employee Advocacy skill (14-day program)`

---

# Final tasks

## Task 19: Register all routers + full test run
- Ensure `bot/handlers/linkedin/__init__.py` `routers` list includes all 12
  routers (menu + 11 skill files; post-audit shares humanizer dir but has its
  own router).
- Run `pytest -q` — all green.
- Manual smoke per `verify` skill: launch the bot, walk Create content → LinkedIn
  → each skill, confirm draft + Publish (manual message) appears.
- **Commit:** `chore: register all linkedin skill routers`

## Task 20: README + cleanup
- Update `README.md` LinkedIn section to describe the 10 skills + manual publish.
- Remove the now-unused `skills/linkedin/system_prompt.txt` / `post_format.txt`
  **only after** confirming nothing imports them (`grep -rn "linkedin/system_prompt"`).
- **Commit:** `docs: document LinkedIn skills; remove legacy prompt files`

---

## Notes for the implementer

- **Async safety**: every `requests`-based call (`fetch_post`, `publish`,
  `apify_client.*`) MUST be wrapped in `await asyncio.to_thread(...)`. Blocking
  the aiogram event loop freezes all users.
- **No live network in tests**: mock `fetch_post`, `publish`, `apify_client`
  methods, and `AsyncAnthropic.messages.create`.
- **Manual publish is the contract for now**: `publish(...)` returns
  `{"mode": "manual", "message": ...}` whenever Publora env vars are unset. Don't
  add real keys to ship.
- **Don't edit vendored libs** beyond import fixes — keep them diffable against
  upstream so a future `git pull` of the skill repo is mergeable.
```
