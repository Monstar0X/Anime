"""End-to-end leech pipeline: download -> extract -> (encode) -> upload -> post.

Two quality strategies are chosen automatically:

* ``direct``  – every requested quality already exists as its own torrent with
  a compatible audio track, so each is leeched and posted as-is.
* ``encode``  – only one quality exists, so the single file is encoded into
  480p / 720p / 1080p while the untouched source is posted as ``HDRip``.

Every step is cancellable through an :class:`asyncio.Event` and reports live
progress to the job's status message.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from os import path as ospath, walk
from time import time

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Var, LOGS
from .bot_instance import bot
from .tordownload import TorDownloader
from .ffencoder import FFEncoder
from .extractor import extract_all
from .reporter import rep
from .search_engine import detect_audio, group_qualities, quality_label
from .metadata import resolve, custom_only, apply_custom, anilist_cover, Metadata
from .caption import build_caption, build_filename, build_file_caption
from .bot_settings import settings
from .func_utils import convertBytes, encode
from .splitter import split_video
from . import thumbs
from . import ui
from .ui import bq, esc, sc

VIDEO_EXTS = (".mkv", ".mp4", ".avi", ".mov", ".webm", ".m4v", ".ts",
              ".m2ts", ".flv", ".wmv", ".mpg", ".mpeg")


def find_video(root: str) -> str | None:
    """Return the largest video file under ``root`` (file or directory)."""
    if ospath.isfile(root):
        return root if root.lower().endswith(VIDEO_EXTS) else None
    best, best_size = None, -1
    for base, _dirs, files in walk(root):
        for name in files:
            if not name.lower().endswith(VIDEO_EXTS):
                continue
            full = ospath.join(base, name)
            size = ospath.getsize(full)
            if size > best_size:
                best, best_size = full, size
    return best


def _default_filename(meta: Metadata, quality: str) -> str:
    """Fallback name used when no template renders (kept simple)."""
    tag = quality_label(quality) or "HDRip"
    title = (meta.title or "Release")[:60].strip()
    return f"{title} [{tag}].mkv"


@dataclass
class LeechJob:
    query: str
    category: str
    primary: object
    siblings: list = field(default_factory=list)
    user_id: int = 0
    custom_meta: dict = field(default_factory=dict)


def _bar(percent: float, width: int = 12) -> str:
    return ui.bar(percent, width)


def _human(speed: float) -> str:
    return f"{convertBytes(int(speed))}/s" if speed else "0 B/s"


class Status:
    """Edits one status message with throttling and renders progress bars."""

    def __init__(self, message, title: str = ""):
        self.message = message
        self.title = title
        self._last = 0.0
        self.cancel_id: int | None = None

    async def _edit(self, text: str, keyboard: InlineKeyboardMarkup | None = None):
        try:
            await self.message.edit_text(
                text, disable_web_page_preview=True, reply_markup=keyboard)
        except Exception:  # noqa: BLE001 - status updates are best effort
            pass

    def _cancel_kb(self) -> InlineKeyboardMarkup | None:
        if self.cancel_id is None:
            return None
        return ui.kb([ui.btn("🚫 ᴄᴀɴᴄᴇʟ", f"fd_cancel_{self.cancel_id}", color=ui.RED)])

    async def update(self, text: str, force: bool = False):
        now = time()
        if not force and now - self._last < 4:
            return
        self._last = now
        await self._edit(text, self._cancel_kb())

    async def progress(self, st, phase: str = "Downloading", force: bool = False):
        now = time()
        if not force and now - self._last < 5:
            return
        self._last = now
        percent = round((st.progress or 0) * 100, 1)
        done, total = st.total_done, st.total_wanted
        speed = st.download_rate
        eta = int((total - done) / speed) if speed else 0
        eta_str = f"{eta // 60}m {eta % 60}s" if eta else "—"
        text = (f"‣ <b>{esc(self.title)}</b>\n"
                f"{bq(f'{sc(phase)} <code>[{_bar(percent)}]</code> {percent}%')}\n"
                f"{bq(f'   {convertBytes(done)} / {convertBytes(total)} · {_human(speed)}' + chr(10) + f'   👥 {st.num_peers} peers · ⬆ {st.num_seeds} seeds · ETA {eta_str}')}")
        await self._edit(text, self._cancel_kb())


async def _download_with_status(magnet: str, name: str, status: Status,
                                label: str, cancel: asyncio.Event | None):
    await status.update(
        f"‣ <b>{status.title or name}</b>\n"
        f"<blockquote><i>Resolving {label}…</i></blockquote>", force=True)
    dl = TorDownloader("./downloads")

    async def on_progress(st):
        await status.progress(st, phase=f"Downloading {label}")

    path = await dl.download(magnet, name, on_progress=on_progress, cancel=cancel)
    if cancel is not None and cancel.is_set():
        return None
    if not path or not ospath.exists(path):
        return None
    # Archive extraction is always on: extract any ZIP/RAR/7z payloads in place.
    await status.update(
        f"‣ <b>{status.title or name}</b>\n"
        f"{bq(sc('extracting archives…'))}", force=True)
    await extract_all(path)
    return find_video(path)


async def _file_thumb(meta: Metadata, query: str = "", category: str = "all") -> str | None:
    """Resolve the thumbnail for the uploaded FILE (not the post)."""
    mode = await settings.get_thumbnail_mode()
    if mode == "off":
        return None
    if mode == "custom":
        return thumbs.custom_thumb_path() or await thumbs.prepare_thumb(
            await settings.get_custom_thumb())
    if mode == "tmdb":
        return await thumbs.prepare_thumb(meta.poster_url)
    if mode == "anilist":
        cover = await anilist_cover(query or meta.title)
        return await thumbs.prepare_thumb(cover or meta.poster_url)
    return thumbs.custom_thumb_path() or None


async def _upload(path: str, quality: str, caption: str, status: Status, name: str,
                  thumb: str | None = None):
    await status.update(
        f"‣ <b>{status.title or name}</b>\n"
        f"{bq(sc('uploading') + f' {quality_label(quality)}…')}", force=True)
    if Var.AS_DOC:
        return await bot.send_document(
            chat_id=Var.FILE_STORE, document=path, thumb=thumb,
            caption=caption, force_document=True)
    return await bot.send_video(
        chat_id=Var.FILE_STORE, video=path, thumb=thumb, caption=caption)


async def _upload_parts(path: str, quality: str, caption: str, status: Status,
                        name: str, cancel=None, thumb: str | None = None
                        ) -> list[tuple[str, int]]:
    """Upload ``path`` (splitting if oversized); return ``[(label, msg_id)]``."""
    parts = await split_video(
        path, on_status=lambda text: status.update(
            f"‣ <b>{status.title or name}</b>\n<blockquote><i>{text}</i></blockquote>",
            force=True),
        cancel=cancel)
    results: list[tuple[str, int]] = []
    label = quality_label(quality)
    for idx, part in enumerate(parts, start=1):
        if cancel is not None and cancel.is_set():
            break
        if len(parts) == 1:
            part_label = label
        else:
            part_label = f"{label} · Part {idx}/{len(parts)}"
        await status.update(
            f"‣ <b>{status.title or name}</b>\n"
            f"<blockquote><i>Uploading {part_label}…</i></blockquote>", force=True)
        msg = await _upload(part, quality, caption, status, name, thumb=thumb)
        results.append((part_label, msg.id))
    return results


_QUALITY_ORDER = ["480", "720", "1080", "HDRip"]


def _qual_rank(quality: str) -> int:
    try:
        return _QUALITY_ORDER.index(quality)
    except ValueError:
        return len(_QUALITY_ORDER)


async def _quality_button(label: str, msg_id: int) -> InlineKeyboardButton:
    # start.py deep links are base64-encoded; encode the same way here.
    payload = await encode(f"get-{msg_id * abs(Var.FILE_STORE)}")
    url = f"https://t.me/{getattr(bot, 'username', '')}?start={payload}"
    return InlineKeyboardButton(label, url=url)


async def _send_post(caption: str, meta: Metadata) -> object:
    """Create the channel post that will hold the download buttons.

    The post always uses the fixed 16:9 brand image (``Var.POST_PIC``); the
    Thumbnail setting only affects the uploaded FILES.
    """
    # Post header = landscape metadata art (16:9) by default, else brand image.
    art = meta.banner_url or meta.backdrop_url or ""
    await thumbs.prepare_post_thumb(art)
    pic = thumbs.post_thumb_path()
    try:
        if pic:
            return await bot.send_photo(Var.POST_CHANNEL, photo=pic, caption=caption)
        return await bot.send_message(Var.POST_CHANNEL, text=caption)
    except Exception as exc:  # noqa: BLE001
        await rep.report(f"Failed to create post: {exc}", "error", log=True)
        return None


async def _add_button(post_msg, buttons: list, label: str, msg_id: int,
                       quality: str = ""):
    """Append a download button, two per row, ordered 480/720 then 1080/HD-RIP."""
    buttons.append({"q": quality, "btn": await _quality_button(label, msg_id)})
    ordered = sorted(buttons, key=lambda x: _qual_rank(x["q"]))
    rows = [ordered[i:i + 2] for i in range(0, len(ordered), 2)]
    try:
        await post_msg.edit_reply_markup(
            InlineKeyboardMarkup([[x["btn"] for x in r] for r in rows]))
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[leecher] button update failed: {exc}")


def _resolve_targets(job: LeechJob, direct: bool) -> list[tuple[str, str]]:
    """Return a list of ``(quality, magnet)`` to process."""
    if direct:
        best = group_qualities(job.siblings + [job.primary])
        targets = []
        for qual in Var.QUALS:
            label = quality_label(qual)
            if label in best:
                targets.append((label, best[label].magnet))
        return targets
    return [(q, job.primary.magnet) for q in Var.QUALS]


def _audio_consistent(job: LeechJob) -> bool:
    """True when every quality of a release carries a compatible audio track.

    Tracks detected as ``unknown`` are ignored, and ``multi`` is treated as a
    superset of ``dual`` so a dual-audio file next to a multi-audio one still
    counts as consistent.
    """
    best = group_qualities(job.siblings + [job.primary])
    signatures: set[frozenset] = set()
    for res in best.values():
        tags = detect_audio(res.title) - {"unknown"}
        if not tags:
            continue
        tags = (tags - {"dual"}) if "multi" in tags else tags
        signatures.add(frozenset(tags))
    return len(signatures) <= 1


async def _resolve_metadata(job: LeechJob) -> Metadata:
    mode = await settings.get_metadata_mode()
    if mode == "off":
        return Metadata(title=job.query, source="filename")
    if mode == "custom":
        return custom_only(job.query, job.custom_meta)
    meta = await resolve(job.query, job.category, name_hint=job.primary.title)
    return apply_custom(meta, job.custom_meta, job.query)


async def run_leech(job: LeechJob, status: Status, cancel: asyncio.Event | None = None):
    def stopped() -> bool:
        return cancel is not None and cancel.is_set()

    meta = await _resolve_metadata(job)
    if stopped():
        await status.update(bq(sc("🚫 cancelled.")), force=True)
        return

    group = group_qualities(job.siblings + [job.primary])
    required = {quality_label(q) for q in Var.QUALS}
    can_direct = required.issubset(set(group)) and _audio_consistent(job)
    direct = can_direct

    template = await settings.get_caption_template()
    name_template = await settings.get_filename_template()
    file_caption_template = await settings.get_file_caption_template()
    file_thumb = await _file_thumb(meta, job.query, job.category)
    targets = _resolve_targets(job, direct)
    if not targets:
        await status.update(bq(sc("❌ no leechable quality found.")), force=True)
        return

    caption = build_caption(
        meta, job.primary.title,
        quality="Multi Quality" if len(targets) > 1 else targets[0][0],
        size_bytes=job.primary.size_bytes,
        template=template,
    )

    post_msg = None
    if await settings.get_bool("auto_post") and Var.POST_CHANNEL:
        post_msg = await _send_post(caption, meta)

    buttons: list = []
    uploaded: list[str] = []
    name = meta.title or job.query

    async def _process(out_path: str, final_qual: str, file_caption: str):
        if stopped():
            return
        try:
            parts = await _upload_parts(out_path, final_qual, file_caption, status,
                                        name, cancel, thumb=file_thumb)
        except Exception as exc:  # noqa: BLE001
            await rep.report(f"Upload failed for {final_qual}: {exc}", "error", log=True)
            return
        if not parts:
            return
        uploaded.append(quality_label(final_qual))
        if post_msg:
            for part_label, msg_id in parts:
                await _add_button(post_msg, buttons, part_label, msg_id,
                                   quality=final_qual)

    if direct:
        group_by_label = group_qualities(job.siblings + [job.primary])
        for qual, magnet in targets:
            if stopped():
                break
            if not magnet:
                continue
            video = await _download_with_status(magnet, name, status,
                                                quality_label(qual), cancel)
            if not video:
                if stopped():
                    break
                await rep.report(f"Download/extract failed for {qual}", "error", log=True)
                continue
            source = group_by_label.get(qual)
            release = getattr(source, "title", "") or job.primary.title
            fname = build_filename(meta, qual, release, name_template)
            fcap = build_file_caption(meta, release, qual, fname,
                                      template=file_caption_template)
            await _process(video, qual, fcap)
    else:
        magnet = job.primary.magnet
        video = await _download_with_status(magnet, name, status, "source", cancel)
        if stopped():
            await status.update(bq(sc("🚫 cancelled.")), force=True)
            return
        if not video:
            await rep.report("Download/extract failed for source", "error", log=True)
        else:
            for qual in Var.QUALS:
                if stopped():
                    break
                filename = build_filename(meta, qual, job.primary.title, name_template)
                try:
                    encoder = FFEncoder(status.message, video, filename, qual,
                                        keyboard=status._cancel_kb())
                    if cancel is not None:
                        watcher = asyncio.create_task(_watch_cancel(cancel, encoder))
                    else:
                        watcher = None
                    out_path = await encoder.start_encode()
                    if watcher:
                        watcher.cancel()
                except Exception as exc:  # noqa: BLE001
                    await rep.report(f"Encode failed for {qual}: {exc}", "error", log=True)
                    continue
                if not out_path:
                    continue
                fcap = build_file_caption(meta, job.primary.title, qual, filename,
                                          template=file_caption_template)
                await _process(out_path, qual, fcap)

    if stopped():
        await status.update(bq(sc("🚫 cancelled.")) + f"\n{bq(esc(name))}", force=True)
    elif uploaded:
        await status.update(
            bq(f"✅ <b>{sc('done')}!</b>") + "\n"
            + bq(f"{esc(name)}\n{sc('qualities')}: {', '.join(uploaded)}"), force=True)
    else:
        await status.update(bq(sc("❌ leech finished with no uploaded files.")), force=True)


async def _watch_cancel(cancel: asyncio.Event, encoder: FFEncoder):
    """Kill the running ffmpeg as soon as the job is cancelled."""
    while not cancel.is_set():
        await asyncio.sleep(2)
    await encoder.cancel_encode()
