"""Build post captions and file names from metadata + configurable templates.

Two templates are used, both editable from ⚙️ Settings:

* **caption template** – the channel-post caption.
* **filename template** – how uploaded files are named.

Placeholders for both: ``{title} {season} {episode} {year} {quality} {audio}
{subtitles} {languages} {genres} {plot} {rating} {status} {filename} {size}
{brand}``.
"""

from __future__ import annotations

import re

from config import Var
from .metadata import Metadata
from .search_engine import detect_audio, detect_subtitles, detect_languages, quality_label
from .func_utils import convertBytes

DEFAULT_TEMPLATE = """<b>{title}</b>
<b>──────────────────────</b>
<blockquote>➥ <b>Sᴇᴀsᴏɴ :</b> {season}
➤ <b>Eᴘɪsᴏᴅᴇ :</b> {episode}
➥ <b>ǫᴜᴀʟɪᴛʏ :</b> {quality}
➤ <b>Aᴜᴅɪᴏ :</b> {audio}
➥ <b>Sᴜʙᴛɪᴛʟᴇs :</b> {subtitles}</blockquote>
<b>──────────────────────</b>
<blockquote>{plot}</blockquote>"""

# ``[S{season}-E{episode}] {title} [{quality}] [{audio}]``
DEFAULT_FILENAME_TEMPLATE = "[S{season}-E{episode}] {title} [{quality}] [{audio}]"

# Caption attached to the uploaded FILES — mirrors the file name by default.
DEFAULT_FILE_CAPTION = "{filename}"

_SXXEXX = re.compile(r"\bS(\d{1,2})[\s._-]?E(\d{1,3})\b", re.IGNORECASE)


def _audio_label(meta: Metadata, release_title: str) -> str:
    if meta.audio:
        return meta.audio
    tags = detect_audio(release_title)
    if "dual" in tags:
        return "Dual Audio"
    if "multi" in tags:
        return "Multi Audio"
    return ", ".join(detect_languages(release_title)) or "Japanese"


def _subtitles_label(meta: Metadata, release_title: str) -> str:
    if meta.subtitles:
        return meta.subtitles
    subs = detect_subtitles(release_title)
    return ", ".join(subs) if subs else "None"


def _values(meta: Metadata, release_title: str, quality: str,
            size_bytes: int, filename: str = "") -> dict:
    return {
        "title": meta.title or "N/A",
        "season": meta.season or "N/A",
        "episode": meta.episode or "N/A",
        "year": meta.year or "N/A",
        "quality": quality_label(quality) or "N/A",
        "audio": _audio_label(meta, release_title),
        "subtitles": _subtitles_label(meta, release_title),
        "languages": ", ".join(detect_languages(release_title)) or "N/A",
        "genres": ", ".join(meta.genres) if meta.genres else "N/A",
        "plot": meta.plot or "N/A",
        "rating": meta.rating or "N/A",
        "status": meta.status or "N/A",
        "filename": filename or release_title,
        "size": convertBytes(size_bytes) if size_bytes else "N/A",
        "brand": Var.BRAND_UNAME,
    }


def _safe_format(template: str, values: dict, fallback: str) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return fallback.format(**values)


def build_caption(meta: Metadata, release_title: str, quality: str,
                  size_bytes: int = 0, template: str = "",
                  filename: str = "") -> str:
    template = template or Var.CAPTION_TEMPLATE or DEFAULT_TEMPLATE
    values = _values(meta, release_title, quality, size_bytes, filename)
    return _safe_format(template, values, DEFAULT_TEMPLATE)


def build_file_caption(meta: Metadata, release_title: str, quality: str,
                       filename: str, size_bytes: int = 0,
                       template: str = "") -> str:
    """Caption for an uploaded FILE. Defaults to the file name itself."""
    template = template or DEFAULT_FILE_CAPTION
    values = _values(meta, release_title, quality, size_bytes, filename)
    return _safe_format(template, values, DEFAULT_FILE_CAPTION)


def build_filename(meta: Metadata, quality: str, release_title: str = "",
                   template: str = "") -> str:
    """Render the file name; empty season/episode brackets are dropped."""
    template = template or Var.FILENAME_TEMPLATE or DEFAULT_FILENAME_TEMPLATE
    values = _values(meta, release_title, quality, 0)
    name = _safe_format(template, values, DEFAULT_FILENAME_TEMPLATE)
    if not meta.season or not meta.episode:
        name = re.sub(r"\[\s*S\s*N/A\s*-\s*E\s*N/A\s*\]", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -_")
    if not name.lower().endswith(".mkv"):
        name = f"{name[:120]}.mkv"
    return name
