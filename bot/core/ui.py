"""Shared UI toolkit — one visual language for every screen.

Everything the bot shows goes through here so menus stay consistent:

* :func:`sc`   – small-caps styling for static words (dynamic data stays raw).
* :func:`bq`   – blockquotes that group related lines together.
* :func:`btn` / :func:`kb` – keyboard builders (with button colours when the
  running Pyrogram build supports them, silently plain otherwise).
* :func:`render` – edit a message in place, swapping between text and photo so
  menus can carry artwork (start image, posters, thumbnails).
"""

from __future__ import annotations

import html
import inspect
import re

from pyrogram.errors import MessageNotModified, RPCError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from config import LOGS

try:  # newer Pyrogram builds ship coloured buttons; older ones do not
    from pyrogram.enums import ButtonStyle
except Exception:  # noqa: BLE001
    ButtonStyle = None

_STYLE_OK = (
    ButtonStyle is not None
    and "style" in inspect.signature(InlineKeyboardButton.__init__).parameters
)

BLUE, GREEN, RED = "primary", "success", "danger"

_SC = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ")
_TAGS = re.compile(r"(<[^>]+>|&[a-zA-Z0-9#]+;)")

# ── glyphs ──────────────────────────────────────────────────────────────────
BACK, HOME, CLOSE = "‹ ʙᴀᴄᴋ", "🏠 ʜᴏᴍᴇ", "✖ ᴄʟᴏsᴇ"
PREV, NEXT = "‹ ᴘʀᴇᴠ", "ɴᴇxᴛ ›"


def sc(text: str) -> str:
    """'Hello <b>World</b>' -> 'ʜᴇʟʟᴏ <b>ᴡᴏʀʟᴅ</b>' (tags and entities kept)."""
    return "".join(
        part if i % 2 else part.lower().translate(_SC)
        for i, part in enumerate(_TAGS.split(text))
    )


def bq(text: str, expandable: bool = False) -> str:
    return f"<blockquote{' expandable' if expandable else ''}>{text}</blockquote>"


def esc(text) -> str:
    return html.escape(str(text or ""))


# ── keyboard ────────────────────────────────────────────────────────────────
def btn(text: str, data: str | None = None, *, url: str | None = None,
        color: str | None = None, raw: bool = False) -> InlineKeyboardButton:
    """Build a button. ``raw=True`` keeps the label exactly as given."""
    label = text if raw else sc(text)
    kwargs = {}
    if color and _STYLE_OK:
        kwargs["style"] = getattr(ButtonStyle, color.upper())
    if url:
        return InlineKeyboardButton(label, url=url, **kwargs)
    return InlineKeyboardButton(label, callback_data=data, **kwargs)


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([list(row) for row in rows])


def home_rows(*extra, back_data: str | None = None, home_data: str = "fd_home",
              home: bool = True):
    """Standard footer: optional extras, then Back / Home / Close.

    ``back_data`` adds a Back button to that target. ``home=False`` drops the
    Home button, for screens that sit directly under the hub where Back and Home
    would lead to the same place. Close is a neutral (uncoloured) button.
    """
    rows = [list(row) for row in extra]
    nav = []
    if back_data:
        nav.append(btn(BACK, back_data, color=BLUE))
    if home:
        nav.append(btn(HOME, home_data, color=GREEN))
    nav.append(btn(CLOSE, "close"))
    rows.append(nav)
    return rows


# ── formatting ──────────────────────────────────────────────────────────────
def bar(percent: float, width: int = 12) -> str:
    filled = int(max(0.0, min(percent, 100.0)) // (100 / width))
    return "█" * filled + "▒" * (width - filled)


def human(size: int) -> str:
    if not size:
        return "?"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} PB"


# ── message rendering (text <-> photo, edited in place) ─────────────────────
def _is_own(message) -> bool:
    """True when ``message`` was sent by the bot (safe to delete/replace)."""
    user = getattr(message, "from_user", None)
    return bool(getattr(user, "is_self", False)) or bool(getattr(message, "outgoing", False))


async def _safe_delete(message) -> None:
    if not _is_own(message):
        return  # never delete the user's own message
    try:
        await message.delete()
    except RPCError:
        pass


async def render(message, text: str, markup: InlineKeyboardMarkup | None = None,
                 image=None, *, keep_photo: bool = True):
    """Show ``text`` on ``message``, editing in place whenever Telegram allows it.

    ``image`` (URL / file_id / path / bytes) turns the message into a photo with
    ``text`` as caption. Editing between text and media is not always permitted,
    so we fall back to sending a fresh message and deleting the old one.
    """
    has_photo = bool(getattr(message, "photo", None))

    if image is not None and keep_photo:
        if has_photo:
            try:
                return await message.edit_caption(text, reply_markup=markup)
            except MessageNotModified:
                return message
            except RPCError:
                pass
        try:
            return await message.edit_media(
                InputMediaPhoto(image, caption=text), reply_markup=markup)
        except MessageNotModified:
            return message
        except RPCError:
            pass
        try:
            new = await message.reply_photo(image, caption=text, reply_markup=markup)
            await _safe_delete(message)
            return new
        except RPCError as exc:  # bad image URL / file_id: degrade to text
            LOGS.warning(f"[ui] photo render failed, using text: {exc}")

    if has_photo:
        new = await message.reply_text(text, reply_markup=markup,
                                       disable_web_page_preview=True)
        await _safe_delete(message)
        return new

    try:
        return await message.edit_text(text, reply_markup=markup,
                                       disable_web_page_preview=True)
    except MessageNotModified:
        return message
    except RPCError:
        return await message.reply_text(text, reply_markup=markup,
                                        disable_web_page_preview=True)
