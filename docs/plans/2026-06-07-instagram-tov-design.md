# Instagram Tone of Voice Extraction

**Date:** 2026-06-07
**Status:** Design — ready for implementation planning

## Goal

Add an alternative to the tone-of-voice wizard: the user sends their public Instagram
profile and the bot extracts a rich tone-of-voice profile from real posts via the
`tov_extractor` microservice (Apify + Claude).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Entry point | Choice screen before wizard | One extra tap, wizard path unchanged |
| Integration | HTTP call to `tov_extractor` microservice | Separation already exists; no logic to duplicate |
| Schema | Store Instagram schema as-is (richer) | More signal for downstream content generation |
| Confirmation | None — auto-save after extraction | Profile is shown in full; no ambiguity |
| Downstream | No changes to LinkedIn/TikTok generators | They receive `tone_profile` as raw JSON; richer schema is additive |

## Repo Structure Change

`backend/` → `tov_extractor/`

The FastAPI app (`main.py`, `scraper.py`, `analyzer.py`) stays as-is inside.

## User Flow

```
action:tone_of_voice
  → choice screen: [ 🧙 Answer a few questions ] [ 📸 Import from Instagram ]

Wizard path — unchanged (role → audience → style words → examples → generate → save)

Instagram path:
  → "Send your Instagram username or profile URL"
  → user sends e.g. @alex or https://instagram.com/alex
  → "Analyzing your Instagram profile… this takes ~1–2 minutes ⏳"
  → POST /analyze to tov_extractor (timeout 180s)
  → auto-save to DB
  → show full formatted profile
  → done
```

Error cases shown inline with offer to start the wizard:
- Private or non-existent profile
- No posts with captions found
- Microservice unreachable

## Instagram Schema (stored as-is)

```json
{
  "username": "alex",
  "posts_analyzed": 47,
  "persona_summary": "...",
  "archetype": "...",
  "voice_dimensions": [{"name": "...", "description": "..."}],
  "language": {"primary": "...", "secondary": null, "mixing_note": null},
  "caption_patterns": [{"name": "...", "frequency": "...", "description": "...", "examples": []}],
  "motifs": {"themes": [], "places": [], "sensory": []},
  "dos": ["..."],
  "donts": ["..."],
  "signature_elements": {"punctuation": "...", "hashtags": "...", "phrases": []}
}
```

## Profile Display Format

Sent as one message (split if > 4096 chars):

```
📸 @username — 47 posts analyzed

👤 Persona: <persona_summary>
🎭 Archetype: <archetype>

🗣 Voice dimensions:
• <name>: <description>

🌍 Language: <primary> / <secondary>

📝 Caption patterns:
• <name> (~freq): <description>

🎯 Themes: <themes>
📍 Places: <places>

✅ Do:
• rule 1

🚫 Don't:
• rule 1

✍️ Style: <punctuation> | <hashtags>
💬 Phrases: "phrase1", "phrase2"
```

## Components

### New state (ToneOfVoiceStates)
- `choosing_method` — waiting for wizard vs Instagram button
- `waiting_instagram_handle` — waiting for username/URL input

### New service: `bot/services/instagram_tov_service.py`
- `analyze(username: str) -> dict` — calls `POST /analyze`, returns the raw JSON
- Timeout: 180s
- Raises `PrivateProfileError`, `NoPostsError`, `ServiceError`

### Handler changes: `bot/handlers/tone_of_voice.py`
- `start_wizard` → `choose_method` — shows entry keyboard, sets `choosing_method`
- New `on_wizard_chosen` — enters existing wizard flow
- New `on_instagram_chosen` — asks for handle, sets `waiting_instagram_handle`
- New `on_instagram_handle` — calls service, saves to DB, shows formatted profile

### New keyboard
- Two-button inline: "🧙 Answer a few questions" / "📸 Import from Instagram"

### Config
- New env var: `INSTAGRAM_TOV_URL` (e.g. `http://localhost:8000`)
