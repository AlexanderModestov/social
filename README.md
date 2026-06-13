# Social Content Bot

Telegram bot for generating LinkedIn posts and TikTok videos with personalized tone of voice.

## LinkedIn skills

From the main menu: **Create content → LinkedIn** opens a submenu of 10 skills
(ported from [sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills), MIT):

| Skill | What it does |
|---|---|
| ✍️ Write post | Drafts a post from your notes/links using a 2026 hook formula |
| 💬 Draft comment | Drafts a comment on a post (paste the post text, or a URL if Apify is configured) |
| ↩️ Draft reply | Drafts a reply to a comment/thread you paste |
| 🧹 Humanize | Strips AI tells from pasted text (modes: strict / aesthetic / forensic) |
| 🔎 Audit | Scores a draft against 2026 algorithm + AI-detection rules (no rewrite) |
| 🪝 Hook extractor | Reverse-engineers a viral post's hook formula + blank template |
| 📊 Engagement | Pulls a post's likers/commenters and groups them by ICP fit (requires Apify) |
| 👤 Profile | Rewrites your pasted headline / About / Experience |
| 🗓 7-day plan | Builds a 7-day content plan from your role + audience |
| 🤝 Advocacy | Plans a 14-day employee-advocacy program |

Generated drafts can be **saved** to your history. Publishing currently runs in
**manual mode** — the bot shows the approved text to copy-paste. Wiring direct
publishing (via Publora) is a follow-up: set `PUBLORA_API_KEY` +
`LINKEDIN_PLATFORM_ID`. Read-side skills (comment/reply/hook/engagement) use
Apify when `APIFY_TOKEN` is set, and otherwise ask you to paste the text.

Skill prompts live under `skills/linkedin/`; the vendored Apify/Publora/URL libs
under `bot/services/linkedin/`.

## Setup

1. Copy `.env.example` to `.env` and fill values
2. Run `docker compose up -d`
3. Run migrations: `docker compose exec bot alembic upgrade head`
4. Bot starts automatically

## Development

```bash
docker compose up        # start bot + postgres
docker compose logs -f bot   # tail logs
pytest                   # run tests
```
