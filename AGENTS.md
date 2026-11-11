# AGENTS.md

Repository-specific knowledge for the finder / leecher Telegram bot.

## What this project is

A Pyrogram (pyrofork) Telegram bot that searches torrent sites, leeches the
selected release, and posts download links. Entry point `main.py` →
`bot/__main__.py`.

The original RSS auto-anime pipeline was removed on purpose (the upstream repo
was only used as a starting point). There is no `BOT_MODE` any more — the bot
is always the finder bot. `bot/plugins/finder.py` drives the UX.

## Layout

- `config.py` — `Var` class, every setting comes from env via `getenv`.
- `bot/core/bot_instance.py` — shared `bot`, `bot_loop`, `sch`, queues.
  Importing it requires a running event loop (uvloop is installed first).
- `bot/core/torrent_sites.py` — torrent provider abstraction. Built-ins +
  `custom_sites.json` driven custom providers. Returns `TorrentResult`.
- `bot/core/search_engine.py` — aggregate search, relevance ranking, category /
  audio / quality detection, filters, multi-quality grouping.
- `bot/core/metadata.py` — AniList (anime) / TMDB (movies, series) metadata,
  anitopy filename fallback.
- `bot/core/caption.py` — caption builder; template editable from the bot.
- `bot/core/extractor.py` — ZIP / RAR / 7z / TAR extraction.
- `bot/core/leecher.py` — download → extract → (encode) → upload → post.
- `bot/core/leech_manager.py` — serial FIFO leech queue (one job at a time)
  with per-job cancellation events.
- `bot/core/tordownload.py` — libtorrent downloader with live progress and
  cancellation (drives libtorrent directly, not the `torrentp` wrapper).
- `bot/core/bot_settings.py` — MongoDB-backed live toggles (thumbnail,
  encoding, direct multi-quality, auto-extract, auto-post) plus
  `metadata_mode` (auto/custom/off) and free-form `custom_meta` overrides.
- `bot/plugins/finder.py`, `bot/plugins/bot_settings_ui.py` — finder UX.

## Handler ordering (important)

Pyrogram's `handler_worker` breaks out of **all** groups on the first matching
handler, and groups run in ascending order. To control precedence:

- `settings_capture` → group `-2` (admin text capture must beat the finder).
- `finder_text` → group `-1` (must beat `channel_post`, which copies non-slash
  text to the DB channel).
- Everything else → group `0`.

When a group `-2`/`-1` handler decides the update isn't its, it must
`raise ContinuePropagation` so lower handlers still see it. `finder_start`
also propagates for deep-link `/start <payload>` so `bot/plugins/start.py`
handles it.

## Quality strategy

- All of 480p/720p/1080p/HDRip present with the same audio → leech each
  **directly** (no encode).
- Only one quality present → encode into 480p/720p/1080p, post the untouched
  source as **HDRip**.

## Conventions / gotchas

- `Var.QUALS` order is `480 720 1080 HDRip`; `ffargs` in `bot/core/ffencoder.py`
  is keyed by the same quality strings. The `HDRip` ffcode is a stream copy.
- Quality display label: 2160/4K/HDRip → `HDRip`; 1080/720/480 stay numeric.
- Deep links: `get-<msg_id * abs(FILE_STORE)>` base64-encoded; handled in
  `bot/plugins/start.py`.
- Python is pinned to 3.10 (`runtime.txt`). Locally the sandbox may have 3.13,
  where `bot.core.bot_instance` can `exit(1)` unless a running loop exists —
  import modules inside an `asyncio.run(...)` when testing.
- `.env` is committed in this repo (already contains live credentials).
- Encode commands must use `-map 0:V -map 0:a? -map 0:s?`. `-map 0:v` also
  matches mjpeg cover art (adds a bogus second video stream) and `-map 0:s`
  aborts the whole run when the source has no subtitle track. `config.py`
  normalizes the old pattern automatically.
- Telegram bots cap uploads at 2000 MiB. Files larger than `MAX_UPLOAD_SIZE`
  (default 1900) are stream-copied into keyframe-aligned parts by
  `bot/core/splitter.py` and each part gets its own `«quality · Part n/m»`
  button. `-fs` is NOT honoured per-segment by the muxer, so the segment
  duration is derived from file size / duration and retried smaller if needed.
- `ffmpeg`/`ffprobe` come from the `static-ffmpeg` dependency when the system
  binaries are missing; `bot/__main__.py` and `bot/core/bot_instance.py` call
  `static_ffmpeg.add_paths()`. `mediainfo` may be absent too — duration falls
  back to `ffprobe`.
- The downloader enables DHT/LSD/UPnP/NAT-PMP, seeds DHT bootstrap nodes and
  merges public trackers into every torrent (magnets often ship with none), so
  0-peer swarms still resolve.
- The sandbox can reset between sessions and wipe the installed Python packages
  (`ModuleNotFoundError: No module named 'dotenv'`), which also kills a running
  bot. Reinstall with `pip install -r requirements.txt` and `pip install
  libtorrent`. `run_supervised.sh` wraps the bot in a loop that reinstalls deps
  if missing and restarts it on exit; launch it detached:
  `setsid ./run_supervised.sh > /dev/null 2>&1 < /dev/null & disown`.

## UI / screens

Every screen is a **panel**: a photo header (brand art or the matched poster)
with a styled caption and coloured buttons. Screens edit the same message in
place where Telegram allows it. All styling goes through `bot/core/ui.py`:

- `sc()` small-caps for static words, `bq()` blockquotes to group lines.
- `btn()` / `kb()` build buttons; button **colours** are applied only when the
  running Pyrogram build supports `ButtonStyle` (pyrofork 2.3.45 does not, so
  they degrade to plain buttons automatically).
- `render()` shows text-or-photo, editing in place; it only ever deletes the
  bot's own messages (never the user's), and falls back to text if an image URL
  is invalid.

Screens: hub (`/start`) → filters → name → results → leech status. Every screen
has a Back / Home / Close footer. `/about` and `/help` open photo panels.
Caption text can exceed Telegram's 1024-char photo-caption limit, so the
results panel drops the photo when the caption is too long.

## Testing

No test framework. Verify changes with `python3 -m py_compile` and small
throwaway scripts that exercise the real code paths (search, detection,
caption, extraction) against live providers.
