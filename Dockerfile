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

# Cache-bust: Railway injects RAILWAY_GIT_COMMIT_SHA per commit. Referencing it
# in a layer immediately before `COPY . .` forces that COPY (and everything
# after) to rebuild on every new commit, so a real code change can never be
# served from a stale cached layer. Also records the commit into the image.
ARG RAILWAY_GIT_COMMIT_SHA=local
RUN echo "Building from commit: ${RAILWAY_GIT_COMMIT_SHA}" > /app/BUILD_COMMIT.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV BUILD_COMMIT=${RAILWAY_GIT_COMMIT_SHA}

CMD ["sh", "-c", "alembic upgrade head && exec python -u -m bot.main"]
