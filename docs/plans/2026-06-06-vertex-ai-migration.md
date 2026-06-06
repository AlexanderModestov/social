# Vertex AI Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move TikTok script generation from the Gemini API-key path (`google-generativeai`) to **Vertex AI** via the new `google-genai` SDK, using a single ADC-based auth path everywhere.

**Architecture:** Replace the API key with GCP project/location config + a service-account-JSON bootstrap that feeds Application Default Credentials. The Gemini service uses a lazy, cached `genai.Client(vertexai=True, ...)` and native async (`client.aio`). The consuming handler (`bot/handlers/tiktok.py`) is unchanged because the response still exposes `.text`.

**Tech Stack:** google-genai SDK, Vertex AI, Application Default Credentials, pydantic-settings, pytest, asyncio

**Design reference:** `docs/plans/2026-06-06-vertex-ai-migration-design.md`

**Prerequisite (manual, before running the bot for real — not required for tests):**
Enable the Vertex AI API on the GCP project, create a service account with the
**Vertex AI User** role, and locally run `gcloud auth application-default login`.

---

### Task 1: Update config with GCP fields + credentials bootstrap

**Files:**
- Modify: `bot/config.py`

**Step 1: Replace `google_api_key` and add the GCP fields + bootstrap**

Replace the entire contents of `bot/config.py` with:

```python
import os
import tempfile
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    anthropic_api_key: str
    gcp_project_id: str
    gcp_location: str = "us-central1"
    google_application_credentials_json: Optional[str] = None
    database_url: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Bootstrap Application Default Credentials in environments (Railway) that pass
# the service-account key as JSON contents rather than a mounted file.
if settings.google_application_credentials_json:
    _sa_path = Path(tempfile.gettempdir()) / "gcp_sa.json"
    _sa_path.write_text(settings.google_application_credentials_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_sa_path)
```

**Step 2: Verify the module imports (with test env)**

Run: `python -c "import os; os.environ['TELEGRAM_BOT_TOKEN']='x'; os.environ['ANTHROPIC_API_KEY']='x'; os.environ['GCP_PROJECT_ID']='x'; os.environ['DATABASE_URL']='sqlite+aiosqlite:///:memory:'; from bot.config import settings; print(settings.gcp_location)"`

Expected: prints `us-central1` with no error.

**Step 3: Commit**

```bash
git add bot/config.py
git commit -m "feat: replace google_api_key with GCP project/location + SA-JSON bootstrap"
```

---

### Task 2: Update conftest and .env.example

**Files:**
- Modify: `conftest.py`
- Modify: `.env.example`

**Step 1: Update `conftest.py`**

The suite loads `bot.config` at import, which now requires `GCP_PROJECT_ID` and
no longer recognizes `GOOGLE_API_KEY`. Replace the `GOOGLE_API_KEY` line:

```python
import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
```

**Step 2: Update `.env.example`**

Replace the `GOOGLE_API_KEY=your_key_here` line with:

```
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1
# Production only — service-account key JSON contents (single line):
# GOOGLE_APPLICATION_CREDENTIALS_JSON=
```

**Step 3: Verify the existing suite still collects and passes**

Run: `pytest -q`
Expected: same result as before this change (no errors from config/import; no
test requires GCP credentials).

**Step 4: Commit**

```bash
git add conftest.py .env.example
git commit -m "chore: point test env and .env.example at GCP_PROJECT_ID"
```

---

### Task 3: Swap the SDK dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Replace the dependency line**

In `requirements.txt`, replace:

```
google-generativeai==0.7.2
```

with:

```
google-genai==1.2.0
```

> If `1.2.0` is unavailable when you run install, use the latest `google-genai`
> release and pin to it. Do **not** keep `google-generativeai` — both must not
> coexist.

**Step 2: Install**

Run: `pip install -r requirements.txt`
Expected: `google-genai` installs; `google-generativeai` is removed/absent.

**Step 3: Verify the new SDK imports**

Run: `python -c "from google import genai; from google.genai import types; print('ok')"`
Expected: prints `ok`.

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: swap google-generativeai for google-genai SDK"
```

---

### Task 4: Rewrite GeminiService for Vertex (lazy client + native async)

**Files:**
- Modify: `bot/services/gemini_service.py`
- Test: `tests/test_gemini_service.py`

**Step 1: Write the failing import-safety test**

The design's key invariant: importing the service and constructing
`GeminiService` must NOT require GCP credentials (so CI stays green). The client
is created lazily and cached. Create `tests/test_gemini_service.py`:

```python
from functools import lru_cache

from bot.services.gemini_service import GeminiService, _get_client


def test_import_does_not_require_credentials():
    # Constructing the service must not touch ADC / network.
    svc = GeminiService()
    assert svc.MODEL == "gemini-2.5-flash"


def test_client_is_lazy_and_cached():
    # _get_client is memoized so the Vertex client is built at most once.
    assert hasattr(_get_client, "cache_clear")  # it's an lru_cache wrapper
```

**Step 2: Run the test to verify it fails**

Run: `pytest tests/test_gemini_service.py -v`
Expected: FAIL — `ImportError: cannot import name '_get_client'` (current module
has no `_get_client`).

**Step 3: Rewrite the service**

Replace the entire contents of `bot/services/gemini_service.py` with:

```python
import json
from functools import lru_cache

from google import genai
from google.genai import types

from bot.config import settings


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )


class GeminiService:
    MODEL = "gemini-2.5-flash"

    async def generate_video(
        self,
        description: str,
        image_paths: list[str],
        tone_profile: dict,
    ):
        system_prompt = (
            "You are a TikTok video creator. Based on the description, images, "
            "and tone of voice, generate a short engaging video (15-60 seconds). "
            f"Tone of voice: {json.dumps(tone_profile)}"
        )
        parts = [types.Part.from_text(text=description)]
        for path in image_paths:
            with open(path, "rb") as f:
                parts.append(
                    types.Part.from_bytes(data=f.read(), mime_type="image/jpeg")
                )

        return await _get_client().aio.models.generate_content(
            model=self.MODEL,
            contents=parts,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
```

**Step 4: Run the test to verify it passes**

Run: `pytest tests/test_gemini_service.py -v`
Expected: PASS (both tests).

**Step 5: Run the full suite for regressions**

Run: `pytest -q`
Expected: all green; no test needs GCP credentials.

**Step 6: Commit**

```bash
git add bot/services/gemini_service.py tests/test_gemini_service.py
git commit -m "feat: rewrite GeminiService on Vertex AI with lazy cached client + native async"
```

---

### Task 5: Manual end-to-end smoke test

> Requires real credentials. Run after `gcloud auth application-default login`
> and with `GCP_PROJECT_ID` set in your environment / `.env`.

**Step 1: Confirm ADC is resolvable**

Run: `gcloud auth application-default print-access-token`
Expected: prints a token (proves local ADC works).

**Step 2: Call the service against Vertex**

Run:
```bash
python -c "import asyncio; from bot.services.gemini_service import GeminiService; print(asyncio.run(GeminiService().generate_video('a coffee shop promo', [], {})).text)"
```
Expected: prints a short generated video script. This proves auth + SDK + model
access in `us-central1` end-to-end.

**Step 3: (Optional) Verify the handler path in the running bot**

Start the bot, trigger the TikTok `video_plot` flow, send a description and
`/done`. Expected: a generated script comes back (the handler was unchanged).

---

## Deployment checklist (Railway)

After merge, in Railway env vars:
- Add `GCP_PROJECT_ID`, `GCP_LOCATION=us-central1`.
- Add `GOOGLE_APPLICATION_CREDENTIALS_JSON` = full contents of the SA key JSON.
- Remove `GOOGLE_API_KEY`.
- `Dockerfile` needs no change (auth is env-var driven; temp file written at runtime).

## Summary

| Task | Files changed |
|------|---------------|
| 1 | `bot/config.py` |
| 2 | `conftest.py`, `.env.example` |
| 3 | `requirements.txt` |
| 4 | `bot/services/gemini_service.py`, `tests/test_gemini_service.py` |
| 5 | manual verification (no file changes) |
