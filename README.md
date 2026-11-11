<p align="center">
  <a href="https://t.me/cantarellabots">
    <img src="https://capsule-render.vercel.app/api?type=waving&color=auto&height=200&section=header&text=CANTARELLABOTS&fontSize=80&animation=fadeIn&fontAlignY=35" />
  </a>
</p>

# 🤖 AutoAnime Bot


A powerful and feature-rich Telegram bot designed for anime distribution and file management. It automates anime fetching, provides a robust file store system, and includes advanced administrative tools.

---

## 🚀 Key Features

- **📺 Auto Anime Fetching**: Automatically fetches and processes the latest anime episodes from RSS feeds.
- **📂 File Store System**: Store files in a private channel and serve them to users via secure deep links.
- **🔗 Link Generation**: Generate single or batch links for files with ease.
- **🛠 Custom Batching**: Create custom batches by selecting specific messages.
- **⏳ Auto-Delete Timer**: Automatically delete sent files after a preset time to manage storage and privacy.
- **🛡 Advanced Force Subscribe**: Supports multiple channels, including "Request to Join" (Join Request) mode.
- **📢 Broadcast System**: Send messages to all bot users at once.
- **🚫 User Management**: Ban/Unban users and manage multiple bot admins.
- **🔍 Global Search**: In-bot search functionality to find files quickly.
- **🎨 Highly Customizable**: Easy to configure banners, pictures, and captions via environment variables.

---

## 🛠 Commands for BotFather

Copy and paste this list into [BotFather](https://t.me/BotFather) `Edit Bot` > `Edit Commands`:

```text
start - Start the bot and get your files
about - Learn more about this bot
help - Get assistance on how to use the bot
search - Search for anime/files in our database
batch - Create a batch link from DB channel
genlink - Generate a single file link
custom_batch - Build a batch by sending messages
broadcast - Send a message to all users
users - See total user statistics
ban - Ban a user from the bot
unban - Unban a previously banned user
add_admin - Authorize a new admin
deladmin - Revoke admin access
admins - List all current admins
pause - Pause the auto-anime fetcher
resume - Resume the auto-anime fetcher
addlink - Add a new RSS source link
addtask - Manually trigger a fetch task
commands - Show the full admin command list
```


---

## 🔍 Finder / Leecher Bot

This is a **search → leech → post** bot with a rich, picture-driven UI.

### Look & feel

Every screen is a **panel** — a photo header (brand art on the hub, the matched
poster on the filter/result screens) with a styled caption and coloured
buttons. Static words use small-caps, related lines sit inside blockquotes, and
the same message is edited in place as you move around. Each screen has a
**‹ Back · 🏠 Home · ✖ Close** footer. A small shared toolkit
(`bot/core/ui.py`) renders all of this, and applies button colours automatically
when the Pyrogram build supports them.

### Flow

1. `/start` → photo hub with **🔍 Find Here**, **⚙️ Settings**, **ℹ️ About**
   and **📖 Help** buttons.
2. Tap **Find Here** → the bot shows **filters as buttons** (all optional;
   nothing selected = search everything):
   - **Type**: Anime · Series · Movies
   - **Audio**: Sub · Dub · Dual · Multi · Hindi · English · Tamil · Telugu
3. Tap **➡️ Next**, then **type the name** (anime / series / movie, a short
   description works too).
4. The name is searched across every configured torrent provider. Results are
   listed **numbered, most relevant first**, each with a quality/audio/size/
   seeder badge, and the header image becomes the matched **poster**.
   A **🎚 Filters** button is available here too, adding **Quality**
   (480p · 720p · 1080p · HDRip).
5. Type the **number** (or tap it) → the job is **queued** and runs when the
   current one finishes. Each status message shows live progress and a
   **🚫 Cancel** button.

Every screen has a **‹ Back** and a **🏠 Home** button, plus a **🔄 Search
again / New name** action, so you never have to run `/start` again. If a search
finds nothing the bot keeps your session and simply asks for another name.

### Magnet links

Tap **🧲 Magnet** (from the filters or name screen) and paste a
`magnet:?xt=urn:btih:…` link. It is leeched, archives extracted and posted
exactly like a search result.

### Leech queue

Leeches run **one at a time** (FIFO). Submitting more jobs while one runs
queues them; each shows its position. Cancelling a queued job removes it,
cancelling the running one stops the torrent and any running encode.

### Metadata modes

Choose from **⚙️ Settings → 🏷 Metadata**:

| Mode | Behaviour |
|------|-----------|
| **Auto** | Fetch title/plot/poster from AniList (anime) or TMDB (movies/series) |
| **Custom** | Use the values you set in the editor (title, season, episode, year, genres, plot, rating, status, poster URL) |
| **Off** | No metadata; only what can be parsed from the filename |

Custom fields also act as overrides on top of Auto when filled in.

### Quality strategy (automatic)

| Situation | What the bot does |
|-----------|-------------------|
| All of 480p / 720p / 1080p / HDRip exist **with the same audio** | Leeches each one **directly** (no re-encode) |
| Only **one** quality exists | Encodes the single file into 480p / 720p / 1080p; the untouched source is posted as **HDRip** |

Files above `MAX_UPLOAD_SIZE` (default 1900 MiB) are automatically split into
playable parts (lossless stream copy), and each part is published as its own
**«quality · Part n/m»** download button.

### Configuration

Add these to `.env` (all optional except `POST_CHANNEL`):

```env
POST_CHANNEL=-1001234567890          # channel where posts are published
TORRENT_SITES=nyaa,subsplease,apibay,eztv,yts
TMDB_API_KEY=                        # optional, for movie/series metadata
METADATA_MODE=auto                   # auto | custom | off
CAPTION_TEMPLATE=                    # optional, overrides the default caption
MAX_UPLOAD_SIZE=1900                 # split files larger than this (MiB)
```

Everything else is toggled **live from the bot**: send `/settings` (or tap
**⚙️ Settings**) to switch on/off thumbnail, encoding, direct multi-quality
leech, auto-extract and auto-post, to pick the metadata mode, edit custom
metadata, and edit the caption template.

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

Then add the `id` to `TORRENT_SITES`. Built-in providers: `nyaa`,
`subsplease`, `apibay` (The Pirate Bay), `eztv`, `yts`, `torrentgalaxy`,
`animetosho`.

---

## 👥 Credits

This project is maintained and developed by:

- **👑 Lead Developer**: [@V_Sbotmaker](https://t.me/V_Sbotmaker)
- **💻 Developer**: [@adityaabhinav](https://t.me/adityaabhinav)
- **🐣 Noob Developer**: [@cantarella_wuwa](https://t.me/cantarella_wuwa)

---

## 📢 Stay Updated

Join our channel for updates, support, and more bots:
👉 **[Cantarella Wuwa](https://t.me/cantarellabots)**

---
*Built with ❤️ using Pyrogram.*
