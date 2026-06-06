# Migrating Gemini from API Key to Vertex AI (google-genai SDK)

**Date:** 2026-06-06
**Status:** Design — ready for implementation planning

## Goal

Move TikTok script generation off the API-key path (`google-generativeai` +
AI Studio key) and onto **Vertex AI**, accessed through the new unified
`google-genai` SDK. This unlocks Google Cloud free credits (which only apply to
Vertex) and gives us the more mature Google Cloud infrastructure.

The migration is intentionally small: one service file, the config, the
dependency list, and deployment env vars. The handler that consumes the service
(`bot/handlers/tiktok.py`) does **not** change.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Platform | Vertex AI (Gemini on GCP), not Agent Engine/ADK | Our use is a single stateless content call; no tools/memory/multi-turn. Vertex gives mature infra + free credits without agent overhead. |
| SDK | `google-genai` (new unified SDK) | Supersedes `google-generativeai`; native async; `vertexai=True` mode. |
| Auth | Application Default Credentials (ADC) | Vertex has no API key. Service-account JSON in prod, `gcloud` user creds locally. |
| Credentials in prod | Service-account JSON key in an env var | Standard pattern for Vertex on a non-GCP host (Railway). |
| Local dev | Same Vertex path (no API-key fallback) | One code path; "local matches prod." One-time `gcloud auth` setup. |
| Region | `us-central1` | Broad model availability, sane default. |
| Client lifecycle | Lazy, cached (`@lru_cache`) | Keeps imports test-safe (no ADC needed to import); first real call still fails fast if creds are wrong. |
| Tests | No SDK-mock unit test; manual smoke test | Mocking an external call here is low-value and brittle. |

## Architecture

```
config.py
  ├─ Settings: gcp_project_id, gcp_location, google_application_credentials_json
  └─ bootstrap (on import): if JSON env var present, write to temp file +
     set GOOGLE_APPLICATION_CREDENTIALS  → ADC can resolve

gemini_service.py
  ├─ _get_client()  @lru_cache  → genai.Client(vertexai=True, project, location)
  └─ GeminiService.generate_video(...)  → await client.aio.models.generate_content(...)
                                          (returns response with .text, unchanged)

tiktok.py  (UNCHANGED — still does `response.text`)
```

### Authentication flow

- **Local:** developer runs `gcloud auth application-default login` once. ADC
  picks up user credentials. `.env` only needs `GCP_PROJECT_ID` (and optionally
  `GCP_LOCATION`).
- **Production (Railway):** `GOOGLE_APPLICATION_CREDENTIALS_JSON` holds the
  service-account key *contents*. The config bootstrap writes it to a temp file
  and points the standard `GOOGLE_APPLICATION_CREDENTIALS` var at it. The
  `genai.Client` reads ADC and finds it. No SDK-level difference between local
  and prod.

The bootstrap lives in `config.py`, immediately after `settings` is
constructed, guaranteeing it runs before any module-level client creation.

## Components

### 1. `bot/config.py`

Remove:

```python
google_api_key: str
```

Add:

```python
from typing import Optional

gcp_project_id: str
gcp_location: str = "us-central1"
google_application_credentials_json: Optional[str] = None
```

Bootstrap (after `settings = Settings()`):

```python
import os, tempfile
from pathlib import Path

if settings.google_application_credentials_json:
    _sa_path = Path(tempfile.gettempdir()) / "gcp_sa.json"
    _sa_path.write_text(settings.google_application_credentials_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_sa_path)
```

### 2. `requirements.txt`

- Remove `google-generativeai`
- Add `google-genai`

### 3. `bot/services/gemini_service.py`

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
        self, description: str, image_paths: list[str], tone_profile: dict,
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

Notes:
- Native async via `client.aio` — the old `asyncio` / `run_in_executor` hack and
  the module-level `genai.configure(...)` are deleted.
- Local image bytes via `Part.from_bytes` (temp files, not GCS) — no Cloud
  Storage dependency.
- Return shape preserves `.text`, so the handler is untouched.

### 4. `.env.example`

- Remove `GOOGLE_API_KEY`
- Add:

```
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1
# Production only — service-account key JSON contents (one line):
# GOOGLE_APPLICATION_CREDENTIALS_JSON=
```

### 5. GCP one-time setup (manual, outside the repo)

1. Enable the **Vertex AI API** on the project.
2. Create a service account with the **Vertex AI User** role.
3. Download its JSON key → paste contents into Railway's
   `GOOGLE_APPLICATION_CREDENTIALS_JSON` env var.

### 6. Railway deployment

- Add env vars: `GCP_PROJECT_ID`, `GCP_LOCATION`,
  `GOOGLE_APPLICATION_CREDENTIALS_JSON`.
- Remove `GOOGLE_API_KEY`.
- `Dockerfile` unchanged — auth is env-var driven, temp file written at runtime.

## Error handling

- **Wrong/missing creds:** the lazy client resolves ADC on first
  `generate_video` call. A bad config surfaces at the first generation (at bot
  boot the first user triggers it), not silently. Errors propagate to the
  existing `try/except` in `on_materials_done`, which already messages the user
  and clears state.
- **Region/model mismatch:** if `gemini-2.5-flash` isn't available in the chosen
  region, the SDK raises on first call; `us-central1` carries it.

## Testing

- **No SDK-mock unit test** — low value, brittle for a single external call.
- **Import safety:** because the client is lazy + cached, importing
  `gemini_service` requires no GCP creds, so the existing `pytest` suite and CI
  (SQLite in-memory) keep working without ADC.
- **Manual smoke test (local, after `gcloud auth application-default login`):**

  ```bash
  python -c "import asyncio; from bot.services.gemini_service import GeminiService; \
print(asyncio.run(GeminiService().generate_video('a coffee shop promo', [], {})).text)"
  ```

  Proves auth + SDK + model access end-to-end.
- **Regression check:** run `pytest` to confirm the config field rename didn't
  break anything touching `settings`.

## Out of scope (YAGNI)

- Agent Engine / ADK / multi-step agents — not needed for a stateless call.
- Workload Identity Federation — overkill on Railway; JSON key is sufficient.
- GCS-based image upload — local `Part.from_bytes` is enough.
- Dual-mode (API key + Vertex) — explicitly rejected for single-path simplicity.

## Summary of changed files

| File | Change |
|------|--------|
| `bot/config.py` | Replace `google_api_key` with GCP fields + credentials bootstrap |
| `requirements.txt` | `google-generativeai` → `google-genai` |
| `bot/services/gemini_service.py` | Lazy cached Vertex client; native async; `Part.from_bytes` |
| `.env.example` | Replace API key with GCP project/location/credentials vars |
| Railway env | Add GCP vars, remove `GOOGLE_API_KEY` |
| `bot/handlers/tiktok.py` | **No change** |
