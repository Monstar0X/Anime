"""libtorrent-backed downloader with live progress and cancellation.

Unlike the old wrapper this drives libtorrent directly so it can report
progress (percent, speed, peers, ETA) and be cancelled mid-flight without
leaking the session.
"""

from __future__ import annotations

import asyncio
import time
from os import path as ospath, walk
from pathlib import Path

import libtorrent as lt

from config import Var, LOGS
from .func_utils import handle_logs

VIDEO_EXTS = (".mkv", ".mp4", ".avi", ".mov", ".webm", ".m4v", ".ts",
              ".m2ts", ".flv", ".wmv", ".mpg", ".mpeg")

# Public trackers merged into every torrent so dead-swarm releases still find
# peers (magnet links often ship with none).
EXTRA_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.tracker.cl:1337/announce",
    "udp://9.rarbg.com:2810/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://open.stealth.si:80/announce",
    "http://tracker.openbittorrent.com:80/announce",
    "https://tracker.tamersunion.org:443/announce",
]

DHT_BOOTSTRAP = [
    ("router.bittorrent.com", 6881),
    ("router.utorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
    ("router.bitcomet.com", 6881),
]


def _largest_video(root: str) -> str | None:
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


class TorDownloader:
    def __init__(self, path: str = "downloads"):
        self._downdir = path
        self._torpath = "torrents"
        self._session: lt.session | None = None
        self._handle = None

    def _ensure_session(self) -> lt.session:
        if self._session is None:
            self._session = lt.session()
            self._session.apply_settings({
                "listen_interfaces": "0.0.0.0:6881,[::]:6881",
                "user_agent": "finder-bot/1.0",
                "enable_dht": True,
                "enable_lsd": True,
                "enable_upnp": True,
                "enable_natpmp": True,
                "announce_to_all_trackers": True,
                "announce_to_all_tiers": True,
                "alert_mask": 0,
            })
            for host, port in DHT_BOOTSTRAP:
                try:
                    self._session.add_dht_node((host, port))
                except Exception:  # noqa: BLE001
                    pass
        return self._session

    def _params(self, torrent: str):
        if torrent.startswith("magnet:"):
            params = lt.parse_magnet_uri(torrent)
        else:
            info = lt.torrent_info(torrent)
            params = lt.add_torrent_params()
            params.ti = info
        params.save_path = self._downdir
        for url in EXTRA_TRACKERS:
            try:
                params.trackers.append(url)
            except Exception:  # noqa: BLE001
                pass
        return params

    @handle_logs
    async def download(self, torrent: str, name: str = None,
                       on_progress=None, cancel: asyncio.Event | None = None) -> str | None:
        Path(self._downdir).mkdir(parents=True, exist_ok=True)
        if not torrent.startswith("magnet:"):
            local = await self._fetch_torfile(torrent)
            if not local:
                LOGS.error("[TorDownloader] could not fetch .torrent file")
                return None
            torrent = local

        session = self._ensure_session()
        try:
            params = self._params(torrent)
        except Exception as exc:  # noqa: BLE001
            LOGS.error(f"[TorDownloader] bad torrent: {exc}")
            return None

        handle = session.add_torrent(params)
        self._handle = handle
        last_data = 0
        last_progress_t = time.time()
        deadline = time.time() + 6 * 60 * 60  # hard ceiling of 6h per torrent
        warned_meta = False
        warned_peers = False

        try:
            while True:
                if cancel is not None and cancel.is_set():
                    LOGS.info("[TorDownloader] cancelled by user")
                    return None
                if time.time() > deadline:
                    LOGS.warning("[TorDownloader] exceeded time ceiling")
                    return None

                st = handle.status()
                if on_progress is not None:
                    try:
                        await on_progress(st)
                    except Exception:  # noqa: BLE001
                        pass

                if not st.has_metadata:
                    # No metadata means DHT/tracker lookups are still running.
                    if not warned_meta and time.time() - last_progress_t > 120:
                        warned_meta = True
                        LOGS.warning(
                            "[TorDownloader] still resolving metadata after 2m "
                            "(no peers found yet)")
                    if time.time() - last_progress_t > 900:
                        LOGS.warning("[TorDownloader] metadata timeout after 15m")
                        return None
                    await asyncio.sleep(2)
                    continue

                if st.total_done != last_data:
                    last_data = st.total_done
                    last_progress_t = time.time()
                    warned_peers = False
                elif not warned_peers and time.time() - last_progress_t > 180:
                    warned_peers = True
                    LOGS.warning(
                        f"[TorDownloader] stalled: {st.num_peers} peers, "
                        f"{st.num_seeds} seeds — no data for 3m")
                elif time.time() - last_progress_t > 1800:
                    LOGS.warning("[TorDownloader] stalled for 30m, giving up")
                    return None

                if st.is_seeding or st.is_finished:
                    break
                await asyncio.sleep(2)

            await asyncio.sleep(1)  # let the last file flush
            return self._locate(handle, name)
        finally:
            try:
                session.remove_torrent(handle)
            except Exception:  # noqa: BLE001
                pass
            self._handle = None

    def _locate(self, handle, name: str | None) -> str | None:
        try:
            info = handle.torrent_file()
            root = ospath.join(self._downdir, info.name()) if info else None
        except Exception:  # noqa: BLE001
            root = None
        if root and ospath.exists(root):
            return _largest_video(root) or root
        if name:
            cand = ospath.join(self._downdir, name)
            if ospath.exists(cand):
                return _largest_video(cand) or cand
        return _largest_video(self._downdir)

    async def _fetch_torfile(self, url: str) -> str | None:
        from aiohttp import ClientSession
        Path(self._torpath).mkdir(parents=True, exist_ok=True)
        save = ospath.join(self._torpath, url.split("/")[-1] or "file.torrent")
        try:
            async with ClientSession() as sess:
                async with sess.get(url) as resp:
                    if resp.status != 200:
                        return None
                    with open(save, "wb") as fh:
                        fh.write(await resp.read())
            return save
        except Exception as exc:  # noqa: BLE001
            LOGS.error(f"[TorDownloader] torrent fetch failed: {exc}")
            return None
