<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=auto&height=200&section=header&text=FINDER%20BOT&fontSize=80&animation=fadeIn&fontAlignY=35" />
</p>

<h1 align="center">🔎 Finder / Leecher Bot</h1>

<p align="center">
A Telegram bot that <b>searches torrents, leeches them, and posts them</b> — with a
rich, picture-driven UI, automatic encoding, metadata and thumbnails.
</p>

---

## ✨ What it does

Finder / Leecher Bot turns a single Telegram chat into a search-and-publish
pipeline:

- **Search** across several torrent providers at once, straight from the bot.
- **Leech** the release you pick — download, extract archives, optionally
  re-encode, then upload.
- **Post** the result to your channel with per-quality download buttons.
- **Decorate** everything with metadata (AniList / TMDB) and thumbnails.

Everything is driven from the chat: filters, settings, metadata, captions and
thumbnails are all live, no restarts.

---

## 🚀 Features

### Search
- Query multiple providers in one go and see results ranked by relevance.
- Filters as buttons: **type** (anime · series · movies) and **audio**
  (sub · dub · dual · multi · hindi · english · tamil · telugu), plus
  **quality** (480p · 720p · 1080p · HDRip) on the results screen.
- Paginated results with quality, audio and size badges.

### Leech
- A **FIFO queue** — leeches run one at a time; extra jobs wait their turn and
  show their position.
- **Live progress** with a cancel button for both queued and running jobs.
- **Automatic archive extraction** (ZIP / RAR / 7z) in place.
- **Automatic encoding**: when only one quality exists, the bot encodes it into
  480p / 720p / 1080p and posts the untouched source as HDRip.
- **Automatic splitting**: files above `MAX_UPLOAD_SIZE` are split into
  playable parts (lossless stream copy) and published as `quality · Part n/m`.
- **Magnet links**: paste a `magnet:?xt=urn:btih:…` link and it is leeched like
  any search result.

### Post
- Posts are published to `POST_CHANNEL` with per-quality **download buttons**
  (secure deep links into your file store).
- The channel post always uses a fixed **16:9 brand image** as its header.
- Optional **auto-post** toggle.

### Metadata
| Mode | Behaviour |
|------|-----------|
| **Auto** | Fetch title / plot / poster from AniList (anime) or TMDB (movies & series) |
| **Custom** | Use the values you set in the editor (title, audio, subtitles, …) |
| **Off** | No metadata; only what can be parsed from the filename |

Custom fields also act as overrides on top of Auto when filled in.

### Thumbnails
The thumbnail is attached to the **uploaded files only** — never to the post.

| Source | Behaviour |
|--------|-----------|
| **AniList** | Cover art from AniList |
| **TMDB** | Poster from TMDB |
| **Custom** | An image you upload from the bot |
| **Off** | No thumbnail |

### Settings (live from the bot)
Send `/settings` (or tap **⚙️ Settings**) to change, without restarting:
metadata mode, thumbnail source, the caption / filename / file-caption
templates, and the auto-post toggle. Encoding and archive extraction are always
on.

---

## 🎛 Commands

Copy this list into [BotFather](https://t.me/BotFather) → `Edit Bot` →
`Edit Commands`:

```text
start - Open the bot hub
about - About this bot
help - How to use the bot
settings - Open the settings menu
batch - Create a batch link from the file store
genlink - Generate a single file link
custom_batch - Build a batch by sending messages
broadcast - Send a message to all users
users - User statistics
ban - Ban a user
unban - Unban a user
banlist - List banned users
add_admin - Authorize a new admin
deladmin - Revoke admin access
admins - List admins
addchnl - Add a force-subscribe channel
delchnl - Remove a force-subscribe channel
listchnl - List force-subscribe channels
fsub_mode - Toggle force-subscribe mode
dlt_time - Set the auto-delete timer
check_dlt_time - Show the current auto-delete timer
pbroadcast - Pin a broadcast
dbroadcast - Delete a broadcast
stats - Bot statistics
ping - Check the bot is alive
```

---

## 🧭 Usage

1. **`/start`** → the photo hub: **🔍 Find Here**, **⚙️ Settings**,
   **ℹ️ About**, **📖 Help**.
2. Tap **Find Here** → pick optional **filters** (type, audio).
3. Tap **➡️ Next** → **type a name** (anime, series, movie, or a short
   description).
4. Pick a result **by number** → the job is queued and runs when the current
   one finishes.
5. When it completes, the bot uploads the files and posts to your channel.

Every screen has **‹ Back · 🏠 Home · ✖ Close** buttons, so you never have to
run `/start` again. If a search finds nothing, your session is kept and the bot
simply asks for another name.

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill it in. Only these are **required**:

```env
API_ID=            # from https://my.telegram.org
API_HASH=          # from https://my.telegram.org
BOT_TOKEN=         # from @BotFather
DB_URI=            # MongoDB connection string
```

Key optional values:

```env
LOG_CHANNEL=-1001234567890     # channel that receives log messages
CHANNEL_ID=-1001234567890      # channel the bot verifies at startup
FILE_STORE=-1001234567890      # channel where uploaded files are stored
POST_CHANNEL=-1001234567890    # channel where finished posts are published
ADMINS=123456789               # space-separated admin user ids
BRAND_UNAME=@Nova_Networks
TORRENT_SITES=nyaa,subsplease,apibay,eztv,yts
TMDB_API_KEY=                  # optional, for movie / series metadata
METADATA_MODE=auto             # auto | custom | off
MAX_UPLOAD_SIZE=1900           # split files larger than this (MiB)
```

See `.env.example` for the full, commented list (channels, encode profiles,
artwork, templates, …).

### Adding your own torrent sites

Edit `custom_sites.json` (see `custom_sites.example.json`). Two kinds are
supported:

```json
{
  "sites": [
    {"id": "mysite", "label": "My Site", "type": "rss",
     "url": "https://example.com/rss?q={query}", "category_hint": "movies"},
    {"id": "myapi", "label": "My API", "type": "json",
     "url": "https://example.com/api/search", "query_param": "q",
     "items_path": "data.results", "title_key": "name",
     "magnet_key": "magnet", "hash_key": "info_hash"}
  ]
}
```

Then add the `id` to `TORRENT_SITES`.

Built-in providers: `nyaa`, `subsplease`, `apibay` (The Pirate Bay), `eztv`,
`yts`, `torrentgalaxy`, `animetosho`.

---

## 🖥 Running

```bash
pip install -r requirements.txt
python3 update.py   # optional: pull upstream updates
python3 -m bot
```

On a platform that expects a start command (Heroku, Render, …), use:

```text
python3 -m bot
```

---

## 🚀 Deploy

This is a **worker** bot (no web port). For free 24/7 hosting see
[DEPLOY.md](DEPLOY.md) — recommended: **Oracle Cloud Always Free** ARM VM with
the included `Dockerfile` / `docker-compose.yml`, plus a free **MongoDB Atlas
M0** cluster for `DB_URI`.

Quick start with Docker:

```bash
cp .env.example .env     # fill it in
docker compose up -d --build
docker compose logs -f
```

---

## 🧱 Project layout

```text
bot/
├── __main__.py          # entry point: startup, restart, queue loop
├── core/
│   ├── bot_instance.py  # shared Pyrogram client, scheduler, queues
│   ├── finder (plugin)  # search → results → queue UX
│   ├── leecher.py       # download → extract → encode → upload → post
│   ├── leech_manager.py # FIFO queue and job state
│   ├── search_engine.py # result parsing, audio/quality detection
│   ├── torrent_sites.py # built-in + custom providers
│   ├── metadata.py      # AniList / TMDB metadata
│   ├── thumbs.py        # thumbnail sources
│   ├── caption.py       # caption / filename templates
│   ├── bot_settings.py  # persistent, live-toggleable settings
│   ├── extractor.py     # archive extraction
│   ├── splitter.py      # large-file splitting
│   ├── ffencoder.py     # ffmpeg encode wrapper
│   ├── database.py      # MongoDB models
│   ├── func_utils.py    # helpers (deep links, messages, …)
│   └── reporter.py      # log-channel reporting
└── plugins/             # auto-loaded handlers (start, admin, finder, …)
```

---

## 👥 Credits

- **Developer**: [OpenHands](https://app.all-hands.dev) — AI software agent
- **Developer**: **Enji Akizuki**

---

## 📄 License

Released under the terms of the [LICENSE](LICENSE) file in this repository.

---

*Built with ❤️ using [Pyrogram](https://docs.pyrogram.org).*
