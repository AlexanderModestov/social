# Social Content Bot

Telegram bot for generating LinkedIn posts and TikTok videos with personalized tone of voice.

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
