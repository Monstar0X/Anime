"""Thumbnail / poster helpers.

Two separate images are involved:

* the **post header** — always the fixed 16:9 brand image (``Var.POST_PIC``).
* the **file thumbnail** — chosen in ⚙️ Settings → Thumbnail, from one of
  three sources: AniList cover, TMDB poster, or a custom image the user sends.
"""

from __future__ import annotations

import io
import os
from os import path as ospath

import httpx

from config import Var, LOGS

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinderBot/1.0)"}
_CUSTOM_THUMB = "custom_thumb.jpg"
_POST_THUMB = "post_thumb.jpg"


def _is_url(value: str) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


async def fetch_bytes(source: str) -> bytes | None:
    """Return image bytes for a URL, local path, or raw ``bytes``."""
    if not source:
        return None
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if _is_url(source):
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=25,
                                         follow_redirects=True) as client:
                resp = await client.get(source)
                resp.raise_for_status()
                return resp.content
        except Exception as exc:  # noqa: BLE001
            LOGS.warning(f"[thumbs] fetch failed {source}: {exc}")
            return None
    if ospath.exists(source):
        with open(source, "rb") as handle:
            return handle.read()
    return None


def _is_landscape(data: bytes) -> bool:
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return True
    try:
        img = Image.open(io.BytesIO(data))
        return img.width >= img.height
    except Exception:  # noqa: BLE001
        return True


def _normalize(data: bytes, size=(320, 320)) -> bytes | None:
    try:
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[thumbs] Pillow missing: {exc}")
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        img = img.convert("RGB")
        img.thumbnail(size)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=90)
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[thumbs] resize failed: {exc}")
        return None


async def _save(source: str, dest: str, size=(320, 320)) -> str | None:
    data = await fetch_bytes(source)
    if not data:
        return None
    if size is None:
        with open(dest, "wb") as handle:
            handle.write(data)
        return dest
    normalized = _normalize(data, size)
    if not normalized:
        return None
    with open(dest, "wb") as handle:
        handle.write(normalized)
    return dest


async def prepare_thumb(source: str) -> str | None:
    """Fetch/resize a thumbnail to the standard path; return the path or None."""
    if not source:
        return None
    return await _save(source, _CUSTOM_THUMB)


async def prepare_post_thumb(source: str = "") -> str | None:
    """Fetch the 16:9 post header image to the standard path.

    Landscape metadata art (AniList banner / TMDB backdrop) is preferred; a
    portrait image is rejected so the post header stays 16:9, falling back to
    the brand image.
    """
    if source:
        data = await fetch_bytes(source)
        if data and _is_landscape(data):
            normalized = _normalize(data, (1280, 720))
            if normalized:
                with open(_POST_THUMB, "wb") as handle:
                    handle.write(normalized)
                return _POST_THUMB
    return await _save(Var.POST_PIC, _POST_THUMB, size=(1280, 720))


def custom_thumb_path() -> str:
    return _CUSTOM_THUMB if ospath.exists(_CUSTOM_THUMB) else ""


def post_thumb_path() -> str:
    if ospath.exists(_POST_THUMB):
        return _POST_THUMB
    return Var.POST_PIC or ""
