# Finder / Leecher Telegram bot — worker image (no web port).
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System tools the bot shells out to:
#   ffmpeg  - encoding / splitting
#   p7zip   - .7z / .zip / .tar extraction
#   unrar-free - .rar extraction (see DEPLOY.md for RAR5 notes)
#   curl    - healthchecks / debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        p7zip-full \
        unrar-free \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install "lxml[html_clean]"

# App code
COPY . .

# Writable scratch dirs for downloads / torrents / encodes / thumbs
RUN mkdir -p downloads torrents encode thumbs && chmod +x run.sh

# Run as an unprivileged user
RUN useradd -m -u 10001 botuser && chown -R botuser:botuser /app
USER botuser

# Persistent mount points (torrent + encode scratch). Override with volumes.
VOLUME ["/app/downloads", "/app/torrents", "/app/encode", "/app/thumbs"]

CMD ["./run.sh"]
