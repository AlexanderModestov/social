FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl wget gnupg libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libxss1 libxtst6 fonts-liberation libappindicator3-1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN playwright install chromium

COPY . .

CMD ["sh", "-c", "alembic upgrade head && python -m bot.main"]
