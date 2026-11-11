"""Persistent, live-toggleable bot settings backed by MongoDB.

Every setting is an on/off switch (or short value) editable straight from the
bot UI, and falls back to the ``config.Var`` defaults on first run.
"""

from __future__ import annotations

from datetime import datetime

from config import Var, LOGS
from .bot_instance import bot  # noqa: F401  (ensures shared client is created)

DEFAULTS = {
    "metadata_mode": Var.METADATA_MODE,
    "thumbnail_mode": getattr(Var, "THUMBNAIL_MODE", "anilist"),
    "auto_post": Var.AUTO_POST,
}

# Feature toggles shown as switches in the settings menu. Auto-extract and
# encoding are always on (no toggle), so they are not listed here.
TOGGLE_LABELS = {
    "auto_post": "📢 ᴀᴜᴛᴏ ᴘᴏꜱᴛ",
}

# Keys that hold a free-form string value instead of a boolean.
TEXT_KEYS = ("caption_template", "filename_template", "file_caption_template",
             "custom_thumb")

# Metadata fields the user can override from the bot (used in "custom" mode).
CUSTOM_META_FIELDS = ("title", "audio", "subtitles")


class Settings:
    def __init__(self):
        self._coll = None
        self._cache: dict = {}
        self._template_cache: str | None = None

    def _collection(self):
        if self._coll is None:
            from .database import db
            self._coll = db.settings
        return self._coll

    async def _load(self):
        if self._cache:
            return
        self._cache = dict(DEFAULTS)
        try:
            doc = await self._collection().find_one({"_id": "bot_settings"})
            if doc:
                self._cache.update({k: v for k, v in doc.items() if k != "_id"})
        except Exception as exc:  # noqa: BLE001
            LOGS.warning(f"[settings] load failed, using defaults: {exc}")

    async def get(self, key: str):
        await self._load()
        return self._cache.get(key, DEFAULTS.get(key))

    async def get_bool(self, key: str) -> bool:
        value = await self.get(key)
        return bool(value) if isinstance(value, bool) else str(value).lower() == "true"

    async def set(self, key: str, value):
        await self._load()
        self._cache[key] = value
        if key == "caption_template":
            self._template_cache = value
        try:
            await self._collection().update_one(
                {"_id": "bot_settings"},
                {"$set": {key: value, "updated_at": datetime.utcnow()}},
                upsert=True,
            )
        except Exception as exc:  # noqa: BLE001
            LOGS.error(f"[settings] save failed: {exc}")

    async def toggle(self, key: str) -> bool:
        new_value = not await self.get_bool(key)
        await self.set(key, new_value)
        return new_value

    async def all(self) -> dict:
        await self._load()
        return dict(self._cache)

    async def get_caption_template(self) -> str:
        await self._load()
        return self._cache.get("caption_template") or Var.CAPTION_TEMPLATE or ""

    async def get_filename_template(self) -> str:
        await self._load()
        return self._cache.get("filename_template") or Var.FILENAME_TEMPLATE or ""

    async def get_file_caption_template(self) -> str:
        await self._load()
        return self._cache.get("file_caption_template") or "{filename}"

    async def get_thumbnail_mode(self) -> str:
        mode = str(await self.get("thumbnail_mode") or "anilist").lower()
        return mode if mode in ("anilist", "tmdb", "custom", "off") else "anilist"

    async def get_custom_thumb(self) -> str:
        await self._load()
        return self._cache.get("custom_thumb") or ""

    async def set_custom_thumb(self, value: str):
        await self.set("custom_thumb", value or "")

    async def get_metadata_mode(self) -> str:
        mode = str(await self.get("metadata_mode") or "auto").lower()
        return mode if mode in ("auto", "custom", "off") else "auto"

    async def get_custom_meta(self) -> dict:
        await self._load()
        meta = self._cache.get("custom_meta") or {}
        return {k: v for k, v in meta.items() if v}

    async def set_custom_meta(self, field: str, value: str):
        await self._load()
        meta = dict(self._cache.get("custom_meta") or {})
        value = (value or "").strip()
        if value:
            meta[field] = value
        else:
            meta.pop(field, None)
        await self.set("custom_meta", meta)


settings = Settings()
