# Veo "Video from Plot" — Quality Patches Design

**Date:** 2026-06-10
**Status:** Approved design, ready for implementation planning
**Flow affected:** TikTok → "🎬 Video from plot" (Veo 3.1 on Vertex AI)
**Files:** `bot/services/gemini_service.py`, `bot/services/veo_service.py`, `bot/handlers/tiktok.py`, `bot/keyboards/inline.py`, `bot/states/states.py`, `bot/config.py`

---

## Background

User reported 7 issues with the Veo video-from-plot flow. Investigation against the
code and the Veo 3.1 / Vertex AI capabilities split them into three buckets:

| # | Symptom | Root cause | Bucket |
|---|---------|-----------|--------|
| 1 | Final video shorter than the prompt; ~10s even for a 20s+ prompt | `duration_seconds=8` is a **hard per-clip cap** on Veo 3.1. A prompt describing 20s of action only gets its first ~8s rendered. | Prompt fix |
| 4 | Duration capped ~24s | `3 scenes × 8s`. Per-clip max is 8s (Veo limit); length only grows by stitching more clips. | Config |
| 3 | On-screen words drift / garbled / nonexistent characters | Generative video models render text unreliably. Intrinsic; must suppress, not fix. | Prompt fix |
| 5 | Vertical 9:16 sometimes flips to landscape | `aspect_ratio="9:16"` is set, but image-to-video **inherits the seed image's** aspect; landscape screenshots drag the output sideways. | Code fix |
| 6 | Only the first attached photo is ever used | By design: `image_paths[0]` is the only seed; other photos go to Gemini for prompt-writing but **never to Veo**. Veo image-to-video takes one init frame. | **Deferred** |
| 7 | Screenshots only land when manually placed in the edited prompt | Same as #6 — Veo can't reproduce real screenshots legibly at chosen moments. That is a montage/compositing job, not a generative one. | **Deferred** |
| 2 | Editing = retype the whole prompt; not flexible | Review gate only offers Accept / manual Edit. | Feature |

### Scope decision

- **This round:** patch the *quality* issues — #1, #2, #3, #4, #5.
- **Deferred to a later session:** #6 / #7 (showing **real screenshots exactly**). This is
  fundamentally a deterministic montage/overlay job (ffmpeg slideshow + caption overlays),
  not something a generative model can do. Veo 3.1 *does* support up to 3 reference images
  ("ingredients-to-video"), which gives a future path — but still stylized, not pixel-exact.
- Photos stay as a **single optional seed**, normalized to 9:16 (see #5).

### Verified Veo 3.1 / Vertex constraints

- `duration_seconds` ∈ {4, 6, 8}. **8s is the hard per-clip maximum.**
- `aspect_ratio` ∈ {"16:9", "9:16"}, but is unreliable when a seed image is supplied.
- Up to 3 reference images supported (relevant only to the deferred screenshot work).

---

## The five patches

### #1 — Prompt matches clip length (prompt-text change)

Teach Gemini that each clip is exactly ~8 seconds so it stops packing a 20s narrative
into one shot. Add to **both** system prompts in `gemini_service.py`
(`write_veo_prompt`, `write_veo_scenes`):

> "This clip is exactly 8 seconds long. Describe only ONE continuous action that
> realistically fits in 8 seconds of screen time. Do not pack a longer story into a
> single shot."

For `write_veo_scenes`, frame it as "each scene is one 8-second shot," so a longer idea
is naturally distributed across scenes instead of being truncated.

### #3 — Suppress garbled on-screen text (prompt-text change)

Add to **both** system prompts:

> "Do NOT depict any on-screen text, captions, words, letters, numbers, logos, signage,
> or UI writing. The scene must contain no readable text of any kind."

When the user later wants real captions, they'll be added as a deterministic ffmpeg
overlay (out of scope here), not rendered by Veo.

### #5 — Lock 9:16 output (code fix, no new dependency)

Two-part guarantee:
1. Keep `aspect_ratio="9:16"` in `VeoService._config()`.
2. **Normalize the seed image to 1080×1920 before sending it to Veo**, so a landscape
   screenshot can't drag the output to landscape.

Use **ffmpeg** (already a dependency) rather than adding Pillow:

```
ffmpeg -y -i <in> -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" <out>
```

New helper `VeoService._normalize_seed(path) -> path` that runs this and returns the
normalized image path; called in `generate_clip` / `generate_and_stitch` before
`types.Image.from_file(...)`. (Cover-crop chosen over letterbox-pad so there are no black
bars; revisit if important content gets cropped.)

### #4 — Make the duration ceiling configurable (config)

Per-clip max is 8s (model limit), so the only lever for total length is scene count.
Promote the magic numbers to `Settings` in `bot/config.py`:

- `veo_duration_seconds: int = 8`  → used in `VeoService._config()`
- `veo_max_scenes: int = 3`  → used wherever scenes are capped
  (`tiktok.py:201` slice `[:3]`, `gemini_service.write_veo_scenes` default `max_scenes=3`,
  `_split_scenes`).

Default stays at 24s (3×8). Raising the ceiling later is a one-line env change, no code
edit. (User was unsure longer videos are needed, so default is unchanged.)

### #2 — Flexible "refine with instructions" editing (feature — the main upgrade)

Turn the one-shot review gate into a loop with three actions.

**New keyboard** `prompt_review_keyboard()` (replace current 2-button version):
- ✅ Accept → `veo:accept`
- 💬 Refine with instructions → `veo:refine`
- ✏️ Rewrite manually → `veo:edit`

**New state:** `TikTokStates.refining_prompt`.

**New service method** `GeminiService.refine_veo_prompt(current, instruction, tone, mode)`:
takes the current prompt(s), a plain-language instruction, the tone profile, and the mode
("quick" | "full"); returns the revised prompt(s). System prompt: "Revise the existing
video prompt according to the user's instruction. Keep everything that wasn't asked to
change. Preserve the 8-second-per-shot and no-on-screen-text constraints. Output only the
revised prompt(s) in the same format."

**New handlers in `tiktok.py`:**
- `veo:refine` → set `refining_prompt`, ask "What should I change? (e.g. 'more energetic,
  sunset lighting, slower camera')".
- message in `refining_prompt` → call `refine_veo_prompt`, store new prompts, **return to
  the same `reviewing_prompt` gate** with the updated preview → loops indefinitely until
  the user hits Accept or Rewrite manually.

This keeps the existing manual-edit path (`veo:edit` → `editing_prompt`) intact and adds
the iterative, conversational refinement the user wanted.

---

## Out of scope (explicitly deferred)

- **#6 / #7 — show real screenshots exactly.** Needs a deterministic montage/overlay path
  (ffmpeg slideshow with Ken-Burns motion + caption overlays) or Veo reference-images.
  Tracked for a future session.

## Test focus

- Prompt-builder unit tests: assert the 8s and no-text constraints appear in system prompts.
- `_normalize_seed`: feed a landscape image, assert output is 1080×1920.
- Refine loop: `refine_veo_prompt` returns same shape (1 prompt for quick, ≤N for full);
  handler returns to `reviewing_prompt`.
- Config: defaults unchanged (8s, 3 scenes); overridable via env.
```
