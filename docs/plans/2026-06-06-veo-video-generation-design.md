# Real TikTok Video Generation with Veo 3.1 (Vertex AI)

**Date:** 2026-06-06
**Status:** Design — ready for implementation planning
**Supersedes:** `docs/plans/2026-06-04-kling-video-generation.md` (to be deleted)

## Goal

Turn the TikTok "Video from plot" flow into one that produces a **real video**
(not a text script), using **Veo 3.1 on Vertex AI** through the same
`google-genai` SDK and ADC auth already in place. No third-party API, no JWT —
Veo is one more method on the existing Vertex client.

Two user-selectable modes:
- **Quick clip** — one 5–8s Veo clip.
- **Full video** — up to 3 scenes, each a Veo clip, concatenated with FFmpeg.

## Why Veo over Kling

| | Veo 3.1 (this design) | Kling (superseded plan) |
|---|---|---|
| API surface | Same `google-genai` SDK + Vertex ADC | New vendor, JWT auth, httpx calls |
| New dependencies | None (FFmpeg only for multi-scene) | PyJWT, httpx orchestration, FFmpeg |
| Auth | Reuses ADC | Separate API key + secret |
| Tone-of-voice | Reused via Gemini prompt-writing | Same |

The user explicitly wants to avoid extra APIs; Veo stays entirely within the
Google/Vertex stack just migrated to.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Generator | Veo 3.1 on Vertex via `client.aio.models.generate_videos` | Same SDK/auth; native async long-running op |
| Modes | Quick clip **and** Full multi-scene | User wants both |
| Mode selection | Sub-choice after "🎬 Video from plot" | Keeps top TikTok menu clean; one extra tap |
| Prompt authoring | Gemini enhances → cinematic Veo prompt(s), tone-aware | Veo quality depends on rich prompts; keeps ToV meaningful |
| Review gate | Accept / Edit before any Veo call, both modes | Veo is slow + metered; never spend on a bad prompt |
| Multi-scene cap | 3 scenes (~18–24s) | Tight cap keeps time/credit burn sane; one constant to raise later |
| Photos | 0, 1, or many allowed | All feed Gemini context |
| Quick-clip seed | First photo → image-to-video; none → text-to-video | Simple, predictable |
| Multi-scene seed | First photo seeds **scene 1** only; scenes 2–3 text-to-video | Veo image-to-video takes one image; mapping photos→scenes is messy |
| Output | Bytes-first, GCS fallback | Avoid managing a bucket unless the model requires it |
| Video format | 9:16 vertical, 8s, native audio on | TikTok-native defaults |

## User Flow

```
/start → Create content → 🎵 TikTok video → 🎬 Video from plot
   → mode picker:  [ ⚡ Quick clip (5–8s) ]   [ 🎬 Full video (≤3 scenes) ]

Quick clip:
  describe idea (+ optional photos) → /done
  → Gemini writes ONE cinematic Veo prompt (tone-aware, sees photos)
  → show prompt  [ ✅ Accept ]  [ ✏️ Edit ]
  → Accept → Veo generate_clip (image-to-video if ≥1 photo, else text-to-video)
  → poll w/ progress → send .mp4

Full video:
  describe idea (+ optional photos) → /done
  → Gemini writes scene-by-scene breakdown (≤3 scenes, tone-aware)
  → show breakdown  [ ✅ Accept ]  [ ✏️ Edit ]
  → Accept → generate_and_stitch:
        scene 1: image-to-video if first photo present, else text-to-video
        scenes 2–3: text-to-video
        → FFmpeg concat → send final .mp4
```

Both modes show progress while polling (e.g. "🎬 Generating… ~2–3 min";
multi-scene edits to "Scene 2/3 rendering…").

## Components

### FSM states (`bot/states/states.py`)
Add to `TikTokStates`: `choosing_video_mode`, `reviewing_prompt`,
`editing_prompt`, `generating_veo`. Reuse `waiting_description`,
`collecting_materials`.

### Keyboards (`bot/keyboards/inline.py`)
- `video_mode_keyboard()` → `⚡ Quick clip` (`videomode:quick`) / `🎬 Full video` (`videomode:full`)
- `prompt_review_keyboard()` → `✅ Accept` (`veo:accept`) / `✏️ Edit` (`veo:edit`)

### GeminiService (`bot/services/gemini_service.py`) — add two prompt writers
Both reuse the lazy Vertex client, return **text** (cheap/fast), tone-aware:
- `write_veo_prompt(description, image_paths, tone_profile) -> str`
- `write_veo_scenes(description, image_paths, tone_profile, max_scenes=3) -> list[str]`
  - Prompt instructs Gemini to output `Scene 1:`…`Scene N:` (≤3); a
    `_split_scenes` helper parses and caps at 3.

The existing `generate_video` (returns a script) is **removed/replaced** — the
flow no longer surfaces a raw script.

### VeoService (`bot/services/veo_service.py`) — NEW, only place touching Veo
- Lazy `@lru_cache` reuse of the shared Vertex client (same pattern as GeminiService).
- `async generate_clip(prompt, seed_image_path=None) -> str` (path to `.mp4`):
  submit via `client.aio.models.generate_videos`, poll
  `client.aio.operations.get` until `done`, resolve bytes (or GCS fallback),
  write temp file.
- `async generate_and_stitch(prompts: list[str], seed_image_path=None) -> str`:
  scene 1 uses `seed_image_path` if given; remaining scenes text-to-video;
  generate **sequentially** (avoid rate limits); FFmpeg `concat` → final `.mp4`.
- `_stitch(clip_paths, tmpdir) -> str`: writes a concat list file, runs
  `ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4`.
- Constants: `VEO_MODEL`, `POLL_INTERVAL=15`, `POLL_TIMEOUT≈360`.

### Handler (`bot/handlers/tiktok.py`)
- `start_video_plot` → set `choosing_video_mode`, show `video_mode_keyboard`.
- mode callbacks → store `video_mode` in FSM, prompt for description (existing
  `waiting_description` → `collecting_materials`).
- `/done` → download photos to temp files → call the matching Gemini writer →
  store prompt(s) → `reviewing_prompt` → show with `prompt_review_keyboard`.
- `veo:accept` → `generating_veo` → quick: `generate_clip`; full:
  `generate_and_stitch` → `answer_video` → cleanup → `state.clear()`.
- `veo:edit` → `editing_prompt` → user sends corrected prompt/scene text → runs Veo.

### Submit + poll (reference)
```python
op = await client.aio.models.generate_videos(
    model=VEO_MODEL,
    prompt=prompt,
    image=types.Image.from_file(location=seed) if seed else None,
    config=types.GenerateVideosConfig(
        number_of_videos=1, duration_seconds=8,
        aspect_ratio="9:16", generate_audio=True,
    ),
)
while not op.done:
    await asyncio.sleep(POLL_INTERVAL)
    op = await client.aio.operations.get(op)
video = op.response.generated_videos[0].video
```
`client.aio` + `asyncio.sleep` keep the bot responsive to other users while a
video renders.

### Output resolution (the one runtime unknown)
**Correction (found during implementation):** `client.files.download(...)` is
**Gemini-Developer-only** — it raises `ValueError` on a `vertexai=True` client.
So the original "try `files.download`" step does not apply on Vertex. The actual
behavior:
1. **No bucket configured (default):** Veo's `generate_videos` response carries
   the clip **inline** — `op.response.generated_videos[0].video.video_bytes` is
   already populated. Write those bytes straight to a temp `.mp4`. No download
   call needed.
2. **GCS output (`GCS_OUTPUT_BUCKET` set):** `output_gcs_uri` is added to the
   config, Veo writes to the bucket, and `video_bytes` is empty. VeoService
   currently **guards this with a clear `RuntimeError`** rather than silently
   failing; fetching from GCS (via `google-cloud-storage` or the returned uri)
   is **deferred** until/unless the inline path proves insufficient.

Task 7's smoke test confirms the inline path works on this project. Implement the
GCS branch only if inline bytes come back empty.

## Config additions (`bot/config.py`, `.env.example`)
- `VEO_MODEL` (default the confirmed Veo 3.1 preview ID; verify against the
  project's Model Garden before wiring — do not hardcode blindly).
- `GCS_OUTPUT_BUCKET: Optional[str] = None` (only used by the GCS fallback).

## Error handling

Veo is slow, metered, and preview — failures are expected and handled gracefully:
- **Clip failure / safety block:** friendly message; return to the prompt-review
  step so the user can Edit (not restart).
- **Timeout:** `POLL_TIMEOUT` per clip → clear message, no infinite hang.
- **Multi-scene partial failure:** abort cleanly, name the failed scene, offer
  retry from review; never send a half-stitched video.
- **FFmpeg missing:** detected at stitch time → clear message.
- **Quota/billing 403:** readable message, not a raw trace (as in the migration
  smoke test).
- All in the handler `try/except` with `state.clear()` so failures never wedge
  the FSM.

## Testing

Mirrors the Vertex-migration philosophy — no brittle SDK-mock for the real call:
- **Unit (no network):** `_split_scenes` + cap-at-3; the FFmpeg concat list-file
  builder; VeoService import-safety (lazy client, no creds to import).
- **Gemini writers:** light test that `write_veo_scenes` caps at 3 and returns a list.
- **No mocked Veo-generation test** (low value/brittle).
- **Manual smoke test (real, gated):** quick-clip text-to-video → `.mp4`;
  quick-clip with photo → image-to-video; full 3-scene → stitched `.mp4`. Also
  confirms model ID + bytes-vs-GCS path.

## Out of scope (YAGNI)
- More than 3 scenes (raise the constant later).
- Per-scene photo seeding beyond scene 1.
- Music/caption overlays, transitions between clips beyond plain concat.
- Kling / any non-Google generator.

## Cleanup
Delete `docs/plans/2026-06-04-kling-video-generation.md` — fully superseded.

## Summary of changed files (for the implementation plan)
| File | Change |
|------|--------|
| `bot/states/states.py` | New TikTok FSM states |
| `bot/keyboards/inline.py` | `video_mode_keyboard`, `prompt_review_keyboard` |
| `bot/services/gemini_service.py` | `write_veo_prompt`, `write_veo_scenes`; remove old `generate_video` |
| `bot/services/veo_service.py` | NEW — Veo generate/poll/download/stitch |
| `bot/handlers/tiktok.py` | Mode picker, review gate, Veo wiring |
| `bot/config.py`, `.env.example` | `VEO_MODEL`, optional `GCS_OUTPUT_BUCKET` |
| `tests/services/test_veo_service.py` | NEW — unit + import-safety |
| `docs/plans/2026-06-04-kling-video-generation.md` | Delete (superseded) |
