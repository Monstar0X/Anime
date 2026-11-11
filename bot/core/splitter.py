"""Split oversized videos into Telegram-uploadable, playable parts.

Telegram bots may upload at most 2000 MiB per file. When a finished video is
larger than ``Var.MAX_UPLOAD_SIZE`` we remux it into keyframe-aligned segments
(``-c copy``, so it is lossless and fast) and return the parts in order.
"""

from __future__ import annotations

import asyncio
import math
from os import path as ospath, makedirs, listdir

from config import Var, LOGS
from .func_utils import mediainfo, convertBytes


def _needs_split(path: str, max_bytes: int) -> bool:
    try:
        return ospath.getsize(path) > max_bytes
    except OSError:
        return False


async def _duration(path: str) -> float:
    """Media duration in seconds, via mediainfo then ffprobe."""
    try:
        value = await mediainfo(path, get_duration=True)
        value = float(value)
        if value > 0:
            return value
    except Exception:  # noqa: BLE001
        pass
    try:
        proc = await asyncio.create_subprocess_shell(
            f"ffprobe -v error -show_entries format=duration -of "
            f"default=nw=1:nk=1 '{path}'",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return float(out.decode().strip())
    except Exception:  # noqa: BLE001
        return 0.0


def _part_paths(out_dir: str, base: str, ext: str) -> list[str]:
    parts = [f for f in listdir(out_dir) if f.startswith(base + ".part")]
    return [ospath.join(out_dir, p) for p in sorted(parts)]


async def _run_segment(src: str, pattern: str, seg_time: int) -> int:
    cmd = (
        f"ffmpeg -hide_banner -loglevel error -i '{src}' -map 0 -c copy "
        f"-f segment -segment_time {seg_time} -reset_timestamps 1 "
        f"'{pattern}' -y"
    )
    LOGS.info(f"[splitter] {cmd}")
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        LOGS.error(f"[splitter] ffmpeg failed: {err.decode().strip()[:500]}")
    return proc.returncode


async def split_video(path: str, max_bytes: int | None = None,
                      on_status=None, cancel=None) -> list[str]:
    """Return a list of parts; a single-element list means no split was needed."""
    max_bytes = max_bytes or Var.MAX_UPLOAD_SIZE * 1024 * 1024
    if not _needs_split(path, max_bytes):
        return [path]

    total = ospath.getsize(path)
    ext = ospath.splitext(path)[1] or ".mkv"
    base = ospath.splitext(ospath.basename(path))[0]
    out_dir = ospath.join(ospath.dirname(path), base + ".parts")
    makedirs(out_dir, exist_ok=True)

    duration = await _duration(path)
    if duration <= 0:
        duration = 1440.0  # assume 24 min; retry loop below corrects it

    # Aim comfortably under the hard cap; stream-copy segments land on
    # keyframes so sizes vary a little either way.
    target = max_bytes * 0.90
    parts_expected = max(2, math.ceil(total / target))
    seg_time = max(int(duration / parts_expected), 30)

    for attempt in range(4):
        for old in _part_paths(out_dir, base, ext):
            try:
                ospath.remove(old)
            except OSError:
                pass
        if on_status:
            await on_status(
                f"✂️ <b>Splitting</b> {convertBytes(total)} into "
                f"{parts_expected} parts…")
        rc = await _run_segment(path, ospath.join(out_dir, f"{base}.part%03d{ext}"), seg_time)
        if rc != 0:
            return [path]

        parts = _part_paths(out_dir, base, ext)
        if cancel is not None and cancel.is_set():
            return parts
        biggest = max((ospath.getsize(p) for p in parts), default=0)
        if parts and biggest <= max_bytes:
            LOGS.info(f"[splitter] {len(parts)} parts, largest {convertBytes(biggest)}")
            return parts
        # Some part was still too big: split more finely and try again.
        parts_expected += 1
        seg_time = max(int(seg_time * 0.8), 15)

    LOGS.warning("[splitter] could not split under the size cap; uploading as-is")
    return [path]
