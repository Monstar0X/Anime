"""Extract archived torrent payloads (ZIP / RAR / 7z / TAR)."""

from __future__ import annotations

import asyncio
import tarfile
import zipfile
from os import path as ospath, walk

from config import LOGS

ARCHIVE_EXTS = (".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz")


def is_archive(filename: str) -> bool:
    low = filename.lower()
    return low.endswith(ARCHIVE_EXTS)


def find_archives(root: str) -> list[str]:
    found: list[str] = []
    if ospath.isfile(root):
        return [root] if is_archive(root) else []
    for base, _dirs, files in walk(root):
        for name in files:
            full = ospath.join(base, name)
            if is_archive(full):
                found.append(full)
    return found


def _extract_zip(archive: str, dest: str) -> bool:
    try:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
        return True
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[extractor] zip failed for {archive}: {exc}")
        return False


def _extract_tar(archive: str, dest: str) -> bool:
    try:
        with tarfile.open(archive) as tf:
            tf.extractall(dest)
        return True
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[extractor] tar failed for {archive}: {exc}")
        return False


async def _extract_7z(archive: str, dest: str) -> bool:
    for tool in ("7z", "7za", "7zr"):
        try:
            proc = await asyncio.create_subprocess_exec(
                tool, "x", archive, f"-o{dest}", "-y",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            if await proc.wait() == 0:
                return True
        except FileNotFoundError:
            continue
    return False


async def _extract_unrar(archive: str, dest: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "unrar", "x", "-y", archive, dest,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await proc.wait() == 0
    except FileNotFoundError:
        return False


async def extract(archive: str, dest: str) -> bool:
    """Extract ``archive`` into ``dest``. Returns True on success."""
    low = archive.lower()
    if low.endswith(".zip"):
        return await asyncio.to_thread(_extract_zip, archive, dest)
    if low.endswith((".tar", ".gz", ".tgz", ".bz2", ".xz")):
        if await asyncio.to_thread(_extract_tar, archive, dest):
            return True
    if await _extract_7z(archive, dest):
        return True
    if low.endswith(".rar") and await _extract_unrar(archive, dest):
        return True
    return False


async def extract_all(root: str) -> list[str]:
    """Extract every archive found under ``root`` (one nesting level)."""
    extracted: list[str] = []
    for archive in find_archives(root):
        dest = ospath.splitext(archive)[0] + "_extracted"
        if await extract(archive, dest):
            extracted.append(dest)
            LOGS.info(f"[extractor] extracted {archive} -> {dest}")
    return extracted
