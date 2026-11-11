"""Serial leech queue.

Jobs run **one at a time** (FIFO). New jobs wait in the queue and their status
message shows the position, so a burst of requests never runs in parallel.
Every job carries a cancellation event that stops the torrent and the encoder.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from config import LOGS
from .reporter import rep


@dataclass
class QueuedLeech:
    id: int
    job: object
    status: object
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    state: str = "queued"  # queued | running | done | cancelled | failed
    position: int = 0

    @property
    def name(self) -> str:
        title = getattr(self.job, "query", "") or getattr(self.job, "primary", None)
        return str(getattr(getattr(self.job, "primary", None), "title", title) or title)


class LeechManager:
    def __init__(self):
        self._queue: asyncio.Queue | None = None
        self._tasks: dict[int, QueuedLeech] = {}
        self._current: QueuedLeech | None = None
        self._worker: asyncio.Task | None = None
        self._seq = 0

    def _q(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    def _ensure_worker(self):
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(), name="leech-worker")

    async def submit(self, job, status) -> QueuedLeech:
        self._seq += 1
        item = QueuedLeech(id=self._seq, job=job, status=status)
        self._tasks[item.id] = item
        self._ensure_worker()
        await self._q().put(item)
        self._reindex()
        return item

    def get(self, tid: int) -> QueuedLeech | None:
        return self._tasks.get(tid)

    def running(self) -> QueuedLeech | None:
        return self._current

    def queued(self) -> list[QueuedLeech]:
        return [t for t in self._tasks.values() if t.state == "queued"]

    def cancel(self, tid: int) -> QueuedLeech | None:
        item = self._tasks.get(tid)
        if not item or item.state in ("done", "cancelled", "failed"):
            return None
        item.cancel.set()
        return item

    def _reindex(self):
        pos = 1
        for item in self._tasks.values():
            if item.state == "queued":
                item.position = pos
                pos += 1

    async def _run(self):
        q = self._q()
        while True:
            item = await q.get()
            try:
                if item.cancel.is_set():
                    item.state = "cancelled"
                    await self._say(item, "🚫 <b>Cancelled</b> before it started.")
                    continue

                item.state = "running"
                item.status.cancel_id = item.id
                self._current = item
                self._reindex()

                from .leecher import run_leech
                await run_leech(item.job, item.status, cancel=item.cancel)
                item.state = "cancelled" if item.cancel.is_set() else "done"
            except Exception as exc:  # noqa: BLE001
                item.state = "failed"
                LOGS.error(f"[leech] job {item.id} failed: {exc}")
                await rep.report(f"Leech job {item.id} failed: {exc}", "error", log=True)
            finally:
                self._current = None
                q.task_done()
                self._reindex()

    @staticmethod
    async def _say(item: QueuedLeech, text: str):
        try:
            await item.status.update(text, force=True)
        except Exception:  # noqa: BLE001
            pass


leech_manager = LeechManager()
