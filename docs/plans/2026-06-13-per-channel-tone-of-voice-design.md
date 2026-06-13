# Per-Channel Tone of Voice — Design

**Date:** 2026-06-13
**Status:** Approved (design)

## Goal

Move from a single global tone of voice (TOV) per user to **one TOV per channel**
(Instagram, TikTok, LinkedIn). The main-menu "Create tone of voice" button only
appears while at least one channel still lacks a TOV, and clicking it lists only
the not-yet-created channels. Once all three exist, the button disappears; a new
`/settings` command is the only place to change an existing TOV. Instagram
becomes a full content channel (it was previously only a TOV import source).

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| TOV ↔ channel model | One TOV per channel, replaceable. Unique on `(user_id, channel)`. |
| Create prompt | Main-menu button shown only while ≥1 channel lacks a TOV; clicking shows a picker of the **not-yet-created** channels. Content creation is never blocked. |
| Managing existing TOVs | `/settings` only (recreate = overwrite, delete = back to "not created"). |
| Instagram | Becomes a full content channel with its own TOV + content flow. |
| TOV build methods | Wizard (all channels) **and** native Apify import for all three channels. |
| Import transport | Unify on the existing `ApifyClient` (`run-sync-get-dataset-items`, retry, cache). Refactor the hand-rolled IG service onto it. |
| Existing TOV rows | **Deleted** in the migration (clean slate). |
| Instagram content | Two sub-types: **Caption from photos** (vision) and **Scenario helper** (conversational → optional Reel). |
| Veo reuse | Extract the shared Veo flow so both TikTok `video_plot` and IG Reel feed it. |

## 1. Data model & repository

`ToneOfVoice` gains a `channel` column (`String(16)`: `"instagram" | "tiktok" |
"linkedin"`). Selection is now by channel, not by `is_active`; the `is_active`
column stays (defaults `True`) to avoid a destructive column change.

**Migration (Alembic):** add `channel` (nullable, then enforce), add a unique
index on `(user_id, channel)`, and **delete all existing TOV rows** (clean
slate — no production data of value, and old rows aren't channel-tagged).

**Repository** (replaces global-active methods):

- `get_for_channel(user_id, channel) -> ToneOfVoice | None`
- `get_channels_with_tov(user_id) -> set[str]` — drives button visibility & picker
- `upsert(user_id, channel, name, profile_json)` — insert or **overwrite** the
  row for that channel (replaces today's `create` + `deactivate_all`)
- `delete(user_id, channel)` — for `/settings`

**Consumers updated:** `get_active_tov()` in `linkedin/_shared.py` →
`get_for_channel(user_id, "linkedin")`; the three `tiktok.py` call sites →
`"tiktok"`; the new IG flow → `"instagram"`. A missing channel TOV stays
graceful — skills run with `{}` as today.

## 2. Unified Apify TOV import layer

A new `bot/services/tov/` package wraps the existing `ApifyClient` transport and
maps each channel to a public, no-cookies profile-scraper actor:

| Channel | Actor | Yields |
|---|---|---|
| Instagram | `apify~instagram-scraper` (already used) | post captions |
| LinkedIn | a profile-posts actor (e.g. `apimaestro~linkedin-profile-posts`) | post bodies |
| TikTok | `clockworks~tiktok-scraper` | video descriptions |

`TovImportService.analyze(channel, handle_or_url)` runs the same pipeline for
every channel:

1. `extract_handle()` — normalize `@name` / profile URL (per-channel regex).
2. `fetch_profile_posts()` — call that channel's actor via `ApifyClient`, cap ~50.
3. `preprocess()` — text, language detection, length/freq stats (generalize the
   current IG `_preprocess_posts`).
4. `generate_tov()` — Claude call with a **channel-tuned prompt + schema**
   (IG: captions/hashtags; LinkedIn: hooks/professional register; TikTok:
   hook/pacing/CTA). Consumers pass raw `profile_json` to Claude, so per-channel
   shapes are fine.

The `PrivateProfileError / NoPostsError / ServiceError` taxonomy is reused for
uniform error messages. The existing `instagram_tov_service.py` is refactored
onto this shared transport with no user-visible behavior change. The **wizard**
stays channel-agnostic and is the fallback when there's no Apify token or a
scrape fails.

## 3. UX & navigation

**Main-menu button (conditional).** On `/start`, query
`get_channels_with_tov(user_id)`. Show "🎭 Create tone of voice" only while a
channel is missing; hide it once all three exist. `main_menu_keyboard()` becomes
a function of the user's TOV set.

**Channel picker.** The button opens a keyboard of **only the channels without a
TOV** (callback `tovchan:<channel>`). Picking one leads to the method choice —
wizard or native import (Section 2).

**Create → save.** Both methods end by calling
`upsert(user_id, channel, name, profile_json)`, then confirm and offer the next
missing channel (or return to a button-less main menu).

**`/settings` (new).** Lists all three channels with status:

- ✅ created → **Edit (recreate)** · **Delete**
- ➕ not created → **Create**

Callbacks `settings:<action>:<channel>`. *Recreate* re-runs the method picker and
overwrites via `upsert`. *Delete* removes the row (channel returns to "not
created", so the main-menu button reappears). This is the only place to change an
existing TOV.

**States.** `ToneOfVoiceStates` gains `choosing_channel`; a `channel` value
threads through FSM data so wizard/import handlers know which channel they build
for. `/settings` reuses the same creation states.

## 4. Instagram content flow

Add Instagram to `platform_keyboard()`. `platform:instagram` opens a sub-type
keyboard:

- **📸 Caption from photos**
- **🎬 Scenario helper**

Both pull the IG TOV via `get_for_channel(user_id, "instagram")` (`{}` if none).

**Caption from photos (vision).** User sends one or more photos → `/done`. The
bot downloads them (reuse TikTok's `_download_photos`) and passes them to a
**vision** call — reusing the already-wired multimodal `GeminiService` (it
already accepts `image_paths`) — to extract what's depicted, then writes a
caption + hashtags in the IG TOV. Shown on the save/regenerate card. The photos
*are* the input; no topic prompt.

**Scenario helper (conversational → optional Reel).** User describes an idea; the
bot co-develops a written Reel **scenario/script** (hook → beats → shot ideas →
caption) in the TOV. Reuses the existing **refine clarify-loop** (the
discriminated `revision | clarify` JSON + `/cancel` escape hatch built for Veo
review) so they iterate until it's right. The finalized scenario is a deliverable
on its own; a **"🎬 Generate Reel"** button optionally feeds it (as the
description) plus any photos into the Veo pipeline.

**Veo reuse.** Both TikTok `video_plot` and IG Reel now feed Veo, so the shared
Veo flow (video-mode → description → materials → prompt review → refine/edit/
accept → generate) is **extracted into `bot/handlers/_veo_flow.py`**,
parametrized by `platform` + `tone_profile`. Per-channel differences are just the
TOV source and the `platform` tag saved to `PostHistory`; prompt copy stays
generic ("vertical short-form video") — no Reel-specific fork now (YAGNI).

**States.** New `InstagramStates`: `waiting_subtype`, `collecting_caption_photos`,
`scenario_developing` (clarify-loop), `scenario_ready`. Reel reuses the extracted
Veo states.

## 5. Testing & rollout

- **DB/repo:** unit tests for `get_for_channel`, `get_channels_with_tov`,
  `upsert` overwrite semantics, and `delete`. Migration drops existing rows.
- **Import layer:** test `extract_handle` per channel and `preprocess` on fixture
  posts; mock the `ApifyClient` transport (no live calls). Reuse the error
  taxonomy assertions.
- **UX:** test the conditional main-menu button (hidden when all three exist),
  the not-created picker, and `/settings` status rendering.
- **Manual smoke:** one wizard + one import per channel; IG photo-caption with a
  real photo; IG scenario → Reel handoff.

## Out of scope (YAGNI)

- Multiple TOVs per channel / TOV versioning.
- Reel-specific Veo prompt fork (generic short-form copy is enough now).
- LinkedIn/TikTok content-flow changes beyond swapping the TOV lookup to
  per-channel.
