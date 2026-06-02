# Social Content Bot — Design Document
_Date: 2026-06-02_

## Overview

A Telegram bot that helps a user create content for LinkedIn and TikTok. It learns the user's tone of voice through a wizard, then generates posts and videos on demand using Claude (Anthropic) and Gemini (Google).

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Telegram framework | aiogram 3.x (async, built-in FSM) |
| Database | PostgreSQL + SQLAlchemy (async) + Alembic migrations |
| LLM — text/post gen | Anthropic Claude API (claude-sonnet-4-6) |
| LLM — video gen | Google Gemini API (gemini-2.0-flash-exp) |
| Browser automation | Playwright (async, Chromium headless) |
| Web scraping | httpx + BeautifulSoup4 |
| Local dev | Docker Compose (bot + postgres) |
| Production | Railway via GitHub (Dockerfile + railway.toml) |

---

## Project Structure

```
social/
├── bot/
│   ├── main.py                  # entry point, router registration
│   ├── handlers/
│   │   ├── start.py             # /start, main menu
│   │   ├── tone_of_voice.py     # wizard flow
│   │   ├── linkedin.py          # linkedin post flow
│   │   └── tiktok.py            # tiktok flow (both sub-paths)
│   ├── keyboards/
│   │   └── inline.py            # all inline keyboard builders
│   ├── states/
│   │   └── states.py            # all FSM state classes
│   ├── services/
│   │   ├── claude_service.py    # Anthropic API wrapper
│   │   ├── gemini_service.py    # Google Gemini API wrapper
│   │   ├── playwright_service.py# screen recording
│   │   └── scraper_service.py   # link → text extraction
│   └── db/
│       ├── models.py            # SQLAlchemy ORM models
│       ├── repository.py        # all DB queries
│       └── session.py           # async session factory
├── skills/
│   ├── brand_voice/             # tone-of-voice prompt files
│   └── linkedin/                # linkedin post prompt files
├── migrations/                  # Alembic
├── Dockerfile
├── docker-compose.yml
├── railway.toml
├── .env.example
└── requirements.txt
```

---

## Database Models

```python
class User(Base):
    telegram_id: int          # PK
    username: str | None
    created_at: datetime

class ToneOfVoice(Base):
    id: int                   # PK
    user_id: int              # FK → User
    name: str                 # e.g. "Professional Alex"
    profile_json: dict        # full structured profile from Claude
    is_active: bool           # one active per user
    created_at: datetime
    updated_at: datetime

class PostHistory(Base):
    id: int                   # PK
    user_id: int              # FK → User
    platform: str             # "linkedin" | "tiktok"
    format: str               # "post" | "product_demo" | "video_plot"
    input_data: dict          # links, notes, description provided
    output_data: dict         # generated text / file path
    created_at: datetime
```

---

## FSM States

```python
class ToneOfVoiceStates(StatesGroup):
    waiting_role         = State()
    waiting_audience     = State()
    waiting_style        = State()
    waiting_examples     = State()
    confirming_profile   = State()

class LinkedInStates(StatesGroup):
    collecting_inputs    = State()   # accumulates until /done
    generating           = State()
    editing              = State()

class TikTokStates(StatesGroup):
    waiting_subtype      = State()   # product_demo | video_plot
    # product demo
    waiting_product_url  = State()
    recording            = State()
    # video plot
    waiting_description  = State()
    collecting_materials = State()   # accumulates until /done
    generating_video     = State()
```

---

## Flow 1: Tone of Voice Wizard

**Trigger:** `/start` → user selects "Create tone of voice"

**Steps:**
1. Role — "What's your professional role / what do you create content about?"
2. Audience — "Describe your audience"
3. Style — inline keyboard: pick 3 words (Formal / Casual / Inspiring / Analytical / Direct / Storyteller)
4. Examples — "Share 1–3 examples of content you like (text, links, or your own posts)" → `/done`
5. Claude synthesizes answers using brand-voice skill prompts → structured JSON profile
6. Bot shows preview → [Save] [Regenerate] [Edit]

**Profile JSON shape:**
```json
{
  "voice_summary": "Direct and analytical with personal stories",
  "tone_words": ["direct", "analytical", "inspiring"],
  "avoid": ["buzzwords", "passive voice", "generic advice"],
  "always": ["lead with a hook", "back claims with data", "end with a question"],
  "audience": "product managers and founders",
  "example_phrases": ["Here's what I learned...", "The data shows..."]
}
```

**Future:** user can select "Update tone of voice" from settings — shorter re-wizard, old profiles preserved in history with `is_active=false`.

---

## Flow 2: LinkedIn Post

**Trigger:** platform selection → LinkedIn

**Steps:**
1. Bot prompts: "Send links and/or notes. Type `/done` when finished."
2. Bot accumulates all messages (links + free text) into a buffer
3. On `/done`:
   - For each link → `scraper_service` extracts article text (httpx + BS4)
   - Assembles: `notes + scraped_content + tone_of_voice_profile`
   - Calls Claude with linkedin-skills system prompt
4. Bot returns formatted post (hook → body → CTA → hashtags)
5. Options: [Copy] [Regenerate] [Edit with feedback] [Save to history]

**Edit loop:** user sends "make it shorter, remove hashtags" → Claude revises with full original context. Loops until user saves or exits.

**LinkedIn post structure (from skills):**
- Hook line (pattern interrupt)
- 3–5 short paragraphs with line breaks
- Call to action
- 3–5 hashtags

---

## Flow 3a: TikTok — Product Demo

**Trigger:** platform selection → TikTok → Product Demo

**Steps:**
1. Bot: "Send me the product URL."
2. User sends URL
3. Bot validates URL, then runs `playwright_service` as async background task:
   - Launch Chromium headless, mobile viewport (390×844)
   - Navigate to URL, wait for `networkidle`
   - Start video recording
   - Scroll through page, interact with key elements (~15s)
   - Save `.mp4` to `/tmp/`
4. Bot sends video file to user, deletes temp file
5. Bot offers: [Generate caption] [Done]
6. Caption generation (optional): Claude scrapes page + tone of voice → punchy TikTok caption + hashtags

**Docker note:** Dockerfile includes `playwright install chromium` + system deps (adds ~500MB; use multi-stage build to keep image lean for Railway).

---

## Flow 3b: TikTok — Video from Plot

**Trigger:** platform selection → TikTok → Video from Plot

**Steps:**
1. Bot: "Describe your video idea."
2. User sends description
3. Bot: "Send photos or materials. Type `/done` to skip."
4. User sends media (optional) then `/done`
5. Bot downloads Telegram media to `/tmp/`
6. Calls Gemini multimodal API with: description + images + tone of voice context + video generation system prompt
7. Bot sends generated video, cleans up temp files
8. Options: [Regenerate] [Adjust description] [Save]

**Gemini service is wrapped** behind a clean interface so the underlying model can be swapped (e.g. to Veo 3) without touching handler code.

---

## Infrastructure

### Local development

```yaml
# docker-compose.yml
services:
  bot:
    build: .
    env_file: .env
    depends_on: [db]
    volumes:
      - .:/app        # hot reload in dev
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: social
      POSTGRES_USER: social
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
```

### Railway deployment

```toml
# railway.toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "python -m bot.main"
restartPolicyType = "on_failure"
```

Railway provides:
- Postgres add-on (connection string injected as `DATABASE_URL`)
- GitHub integration — push to `main` → auto-deploy

### Environment variables

```
TELEGRAM_BOT_TOKEN=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
DATABASE_URL=postgresql+asyncpg://...
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| `/done` pattern for input collection | Yes | Lets users send multiple messages naturally |
| Tone of voice injected into every generation call | Yes | Consistent voice across all content types |
| Playwright runs as async background task | Yes | Doesn't block bot's event loop |
| Gemini wrapped in service class | Yes | Easy model swap as Google releases better video models |
| Old tone of voice profiles kept | Yes | User can revert or compare profiles |
| Post history saved | Yes | Future: show user their content library |

---

## Out of Scope (v1)

- Web dashboard
- Scheduling / posting directly to LinkedIn/TikTok
- Multi-user tone of voice profiles (one active per user is enough)
- Redis for FSM state (in-memory is fine until scale requires it)
- Audio/voiceover generation for TikTok videos
