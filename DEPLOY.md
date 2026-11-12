# Deploying the Finder / Leecher Bot for free

This bot is a **worker** (no web port, no HTTP traffic). It needs:

| Resource | Why | Minimum |
|----------|-----|---------|
| Always-on process | Telegram polling + torrent seeding | 24/7, no sleep |
| RAM | ffmpeg encoding | ~1 GB (2 GB comfortable) |
| Disk | torrents + extracted files + encodes | ~5–10 GB |
| ffmpeg | encoding / splitting | bundled in the image |
| 7z + unrar | archive extraction | bundled in the image |
| MongoDB | users, files, settings | free Atlas M0 |

That mix is why the usual "free web app" hosts don't fit. Below are the free
options that actually work, best first.

---

## 1. MongoDB Atlas (free, do this first)

1. Sign up at <https://www.mongodb.com/cloud/atlas/register> (no card).
2. Create a **free M0** cluster (any region near your VM).
3. **Database Access** → add a user (username + password).
4. **Network Access** → add your VM's public IP (or `0.0.0.0/0` to start).
5. **Connect → Drivers** → copy the string, e.g.
   `mongodb+srv://user:pass@cluster0.xxxx.mongodb.net/?retryWrites=true&w=majority`
6. Put it in `.env` as `DB_URI=` and set `DB_NAME=Cluster0`.

---

## 2. Recommended: Oracle Cloud "Always Free" ARM VM

The only free tier with enough RAM/disk (up to **4 CPU / 24 GB RAM / 200 GB**).

1. Sign up at <https://www.oracle.com/cloud/free/> (needs a card for ID, not charged).
2. Create an instance:
   - Shape: **VM.Standard.A1.Flex** (Ampere ARM) — e.g. 2 OCPU / 12 GB
   - Image: **Ubuntu 22.04**
   - Add your SSH public key, note the public IP.
3. Open the firewall for SSH only (you don't need any inbound app ports).
4. SSH in and install Docker:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
   sudo usermod -aG docker "$USER" && newgrp docker
   ```
5. Clone your repo (or upload the project) and configure:
   ```bash
   git clone <your-repo-url> anime && cd anime
   git checkout V2
   cp .env.example .env
   nano .env          # fill in API_ID, API_HASH, BOT_TOKEN, DB_URI, channels, ADMINS
   ```
6. Build and run:
   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```
7. Auto-start on reboot is handled by `restart: unless-stopped`.

> Note: the bot is CPU- and network-heavy while seeding. On the ARM free tier
> that is fine; keep `MAX_UPLOAD_SIZE` modest (e.g. 1900) so encodes finish.

---

## 3. Google Cloud free `e2-micro` VM

Always-free in `us-west1`, `us-central1`, `us-east1` — but only **1 GB RAM /
30 GB disk**, so it is tight for ffmpeg.

1. Create a **Compute Engine → e2-micro** instance, Ubuntu 22.04, 30 GB disk.
2. Same Docker install as above.
3. Add swap so encodes don't get OOM-killed:
   ```bash
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```
4. In `.env`, lower the pressure: `MAX_UPLOAD_SIZE=700`, and leech one job at a time.

---

## 4. Run it locally (Docker)

```bash
cp .env.example .env     # fill it in
docker compose up -d --build
docker compose logs -f
```

Stop / restart:

```bash
docker compose down
docker compose up -d
```

---

## 5. Run it without Docker

```bash
sudo apt install -y ffmpeg p7zip-full unrar-free
pip install -r requirements.txt && pip install "lxml[html_clean]"
python3 -m bot
```

Keep it alive with **systemd**. Create `/etc/systemd/system/anime-bot.service`:

```ini
[Unit]
Description=Anime Finder Bot
After=network-online.target

[Service]
WorkingDirectory=/opt/anime
EnvironmentFile=/opt/anime/.env
ExecStart=/usr/bin/python3 -m bot
Restart=always
RestartSec=10
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now anime-bot
journalctl -u anime-bot -f
```

---

## Notes & gotchas

- **Never commit `.env` or `*.session`.** They hold your bot token, API keys
  and a logged-in Telegram session. `.dockerignore` and `.gitignore` already
  exclude them from the image; untrack them from git with:
  ```bash
  git rm --cached .env bot/FinderBot.session
  ```
- **Self-update is off by default.** `update.py` only pulls a remote repo when
  `AUTO_UPDATE=true` **and** `UPSTREAM_REPO` are set. Leave them unset so a
  deploy can never overwrite your code.
- **RAR5 archives:** Debian's `unrar-free` cannot extract RAR5. If you hit that,
  install `unrar` (non-free) on the host, or extract on the fly with `7z` which
  handles most RARs.
- **Two bot instances must not run at once** on the same `BOT_TOKEN` — Telegram
  will reject the second. Stop the old one before starting a new one.
- **RAM cap:** `docker-compose.yml` sets `mem_limit: 2g`. Raise it on a bigger
  VM if you encode large 1080p files.
