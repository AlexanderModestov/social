# LinkedIn Skills Port — Design

**Date:** 2026-06-11
**Status:** Approved (design)
**Source:** [sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills) (MIT)

## Goal

Port all 10 LinkedIn marketing skills from the `linkedin-skills` repo into the
Telegram bot, replacing the single "💼 LinkedIn post" button with a full
LinkedIn skill menu. Skills run **on-demand, request/response** — no background
jobs. Publishing uses **manual mode** (copy-paste + target URL) now, with the
repo's backend-selector tiering vendored so real Publora publishing is a later
config change, not a rewrite.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Scope | Full port: all 10 skills. |
| Publishing | Manual-publish now (Tier-0 copy-paste). Vendor `backend_selector` for later Publora wiring. |
| Engagement Monitor | On-demand only (no background scheduler / tracking tables). |
| Detector test scripts | Skipped (need extra paid API keys; Humanizer's value is the rewrite). |
| Generation model | `claude-sonnet-4-6` (matches the rest of the bot). |

## Integration approach: port, don't embed

The repo's skills are written for an *agentic* host (Claude Code/Codex reads
`SKILL.md`, decides which `lib/` function to call, prompts the user). The bot is
aiogram with hard-coded flows, and `ClaudeService` already follows a
"load a skill file as the system prompt, then call Claude" pattern. So we port
the skills' **content** + **pure-Python libs** and drive the workflow from
aiogram handlers, using Claude only for generation steps.

- **Prompt material** → vendor `SKILL.md` + `references/*.md` into the repo's
  `skills/` tree. A loader inlines each `SKILL.md` plus the files it cites into
  one system prompt, prepended with the global voice rules and the user's active
  tone-of-voice profile.
- **Libs** → vendor `url_parser.py`, `apify_client.py`, `publora_client.py`,
  `backend_selector.py` essentially verbatim (self-contained, MIT) into
  `bot/services/linkedin/`. The bot becomes the "generic Python agent runtime"
  the repo README describes.
- **Reads** (post bodies, comments, engagers) → Apify when `apify_token` is set
  (already in config), else fall back to "paste the text." Matches repo behavior.
- **Publish** → `backend_selector` resolves to manual mode now (show approved
  text + target URL). Real Publora later = set env tier, no rewrite.

## Skill catalog & menu

Replace the single LinkedIn button with a **LinkedIn submenu** (from
"✍️ Create content → LinkedIn"), grouped by intent:

**✍️ Create**
- **Post Writer** — topic/notes/links (+ optional formula F1–F10) → drafted post.
  *Upgrades the existing flow.*
- **Comment Drafter** — post URL → reads post (Apify/paste) → drafted comment.
- **Reply Handler** — comment URL → reads thread (Apify/paste), handles 2-level
  flattening → drafted reply.

**🧹 Improve** (operate on pasted text — no scraping)
- **Humanizer** — paste draft → strips AI tells, adds specifics. Mode:
  strict/aesthetic/forensic.
- **Post Audit** — paste draft → scored report vs 2026 algorithm + AI-detection
  checklist (no rewrite).

**🔍 Analyze**
- **Hook Extractor** — viral post URL/text → reverse-engineered formula + blank
  template.
- **Engagement Monitor** — post URL → on-demand engager pull (ICP grouping) +
  threads needing replies. *No background tracking.*
- **Profile Optimizer** — profile URL/pasted sections → rewritten
  headline/About/Featured/Experience.

**🗓 Plan**
- **Content Planner** — role+audience → 7-day plan (topics, formats, hooks, times).
- **Employee Advocacy** — team context → 14-day launch + cadence + governance.

Every "Create" skill ends in a shared **approval card** (draft + char count +
posting-window suggestion) with **Regenerate / Edit / Save / Publish**, reusing
the existing `post_actions_keyboard` pattern. Improve/Analyze/Plan skills output
a report and offer **Save**. `Publish` runs `backend_selector` (manual now).

## Handlers, states & shared mechanics

**Router layout** — one router per skill, mirroring `handlers/linkedin.py`:
```
handlers/linkedin/menu.py          ← submenu + callback routing
handlers/linkedin/post_writer.py
handlers/linkedin/comment.py
handlers/linkedin/reply.py
handlers/linkedin/humanizer.py
handlers/linkedin/audit.py
handlers/linkedin/hook_extractor.py
handlers/linkedin/engagement.py
handlers/linkedin/profile.py
handlers/linkedin/planner.py
handlers/linkedin/advocacy.py
```
Each registered in `main.py`.

**States** — a `StatesGroup` per skill in `states.py`, following one of two shapes:
- *Collect → generate → review* (Create skills): `collecting_inputs` → `editing`
  (reuses today's `LinkedInStates` shape).
- *One-shot input → output* (Improve/Analyze/Plan): single `waiting_input`,
  then terminal report.

**Shared helpers** (avoid duplicating across 10 skills):
- `_resolve_source(text)` — runs `url_parser`; if a LinkedIn URL and
  `apify_token` set, fetch via `apify_client`; else ask the user to paste and
  capture the next message. Backs Comment, Reply, Hook Extractor, Engagement,
  Profile.
- `_approval_card(draft, formula=None)` — formats draft + char count + posting
  window, attaches the actions keyboard.
- `_run_skill(skill, inputs, tov, previous, feedback)` — calls
  `LinkedInSkillService`.

**Card actions** — reuse `post:regenerate / post:edit / post:save`, add
`post:publish`. Edit = free-text feedback → regenerate with
`previous_post`+`feedback`. Humanizer card carries a mode toggle.

**Backwards-compat** — repoint the current `platform:linkedin` callback to the
new submenu; Post Writer preserves the existing collect-links/notes-then-`/done`
UX.

## Prompt loader & `LinkedInSkillService`

**Vendored layout** (under existing `skills/`):
```
skills/linkedin/
  references/            ← shared: hook-formulas.md, voice-rules.md,
                            algorithm-heuristics.md,
                            engagement-metrics-taxonomy.md,
                            industry-benchmarks.md
  post-writer/SKILL.md (+ references/)
  comment-drafter/SKILL.md (+ references/)
  ...                    ← one dir per skill
```
Copy the repo's `SKILL.md` + `references/*.md` verbatim. Resolve the stale
"this file moved" stubs to the real root-level references at copy time.

**`SkillPromptLoader`** — given a skill name:
1. Read that skill's `SKILL.md`.
2. Resolve every `../../references/x.md` and `references/x.md` link and inline
   the file body under a `# Reference: x` heading.
3. Prepend the **global voice rules** (6 rules from the repo root `SKILL.md`) and
   the **user's active tone-of-voice profile** (`ToneOfVoiceRepository.get_active`).
4. Cache the assembled string per skill (static files; cache resets on restart).

System prompt = global voice + user ToV + SKILL.md instructions + inlined
references. Same "skill as system prompt" pattern `ClaudeService` already uses.

**`LinkedInSkillService`** (`bot/services/linkedin/skill_service.py`):
- `async def run(skill, user_inputs: dict, tov: dict, previous=None,
  feedback=None) -> str`
- system = loader output; user = structured `user_inputs` (topic, scraped text,
  formula choice, etc.) + `previous`/`feedback` on regenerate/edit.
- `claude-sonnet-4-6`, `max_tokens` per skill (post ~2048, plan ~4096).
- Post Writer injects the chosen formula skeleton; if none, the model suggests
  2–3 (per the SKILL).

`ClaudeService.generate_linkedin_post` is refactored to delegate here (single
code path).

## Dependencies, config, data

- **Async safety** — vendored libs use synchronous `requests`; wrap every
  Apify/Publora call in `asyncio.to_thread(...)` so a blocking HTTP call never
  freezes the event loop. Add `requests` to `requirements.txt` if not already
  resolved transitively.
- **Config** — add `publora_api_key` and `linkedin_platform_id` as
  `Optional[str]` to `Settings` (unset → `backend_selector` returns manual mode,
  i.e. today's behavior). No secrets needed to ship.
- **Data / history** — reuse `PostHistory` as-is: `platform="linkedin"`,
  `format=<skill>`, `input_data`/`output_data` JSON. **No migration.**

## Testing (TDD)

- `url_parser` — port the repo's example cases as assertions.
- `SkillPromptLoader` — references inlined, voice rules + ToV prepended, stale
  stubs resolved.
- `LinkedInSkillService` — mocked Anthropic client; correct prompt + inputs.
- Handler smoke tests in the style of existing `tests/`. Apify/Publora fully
  mocked — no live network in tests.

## Rollout — independently-mergeable phases

1. **Foundation** — vendor libs + references + loader + `LinkedInSkillService` +
   submenu; refactor Post Writer onto it (replaces current flow).
2. **Improve** — Humanizer, Post Audit (pure paste-in; fastest wins).
3. **Read-side** — Comment, Reply, Hook Extractor, Engagement Monitor, Profile
   Optimizer (share `_resolve_source`).
4. **Plan** — Content Planner, Employee Advocacy.

## Out of scope (YAGNI)

- Per-user Publora credentials and real auto-publishing (manual mode now).
- Background engagement tracking / scheduler / tracking tables.
- AI-detector (GPTZero/Originality/etc.) test harness scripts.
- Cross-platform publishing (X, Threads, Instagram via Publora).
