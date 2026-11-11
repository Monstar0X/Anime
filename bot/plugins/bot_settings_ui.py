"""Settings menu: metadata, thumbnail source, caption & filename templates.

Everything is a button. Text-entry screens (custom metadata values, caption
template, filename template) capture the next message from the user, then
return to the menu — this works for every user, not just admins.
"""

from __future__ import annotations

import time

from pyrogram import ContinuePropagation, filters
from pyrogram.types import CallbackQuery, Message

from config import Var
from bot.core.bot_instance import bot
from bot.core import ui
from bot.core.ui import BACK, bq, btn, esc, kb, sc
from bot.core.bot_settings import settings, TOGGLE_LABELS, CUSTOM_META_FIELDS
from bot.core.caption import (DEFAULT_TEMPLATE, DEFAULT_FILENAME_TEMPLATE,
                              DEFAULT_FILE_CAPTION)
from bot.core import thumbs
from bot.core.reporter import rep
from bot.core.access import DENY, is_admin

# user_id -> ("caption" | "filename" | "custom_thumb" | "meta:<field>")
_pending: dict[int, str] = {}
_pending_at: dict[int, float] = {}
_PENDING_TTL = 300  # seconds; stale prompts must not swallow later text

_MODE_LABEL = {"auto": "🤖 ᴀᴜᴛᴏ", "custom": "✍️ ᴄᴜsᴛᴏᴍ", "off": "🚫 ᴏꜰꜰ"}

_THUMB_LABEL = {
    "anilist": "🌸 ᴀɴɪʟɪsᴛ",
    "tmdb": "🎬 ᴛᴍᴅʙ",
    "custom": "🖼 ᴄᴜsᴛᴏᴍ",
    "off": "🚫 ᴏꜰꜰ",
}

_FIELD_LABEL = {
    "title": "📌 ᴛɪᴛʟᴇ",
    "audio": "🎧 ᴀᴜᴅɪᴏ",
    "subtitles": "🈶 sᴜʙᴛɪᴛʟᴇs",
}


def _back(data: str):
    return kb([btn(BACK, data, color=ui.BLUE)])


def _await(user_id: int, kind: str) -> None:
    """Mark that ``user_id``'s next message is input for ``kind``."""
    _pending[user_id] = kind
    _pending_at[user_id] = time.time()


def _consume(user_id: int) -> str | None:
    """Return the pending kind if it is still fresh, else clear it."""
    kind = _pending.get(user_id)
    if not kind:
        return None
    if time.time() - _pending_at.get(user_id, 0) > _PENDING_TTL:
        _pending.pop(user_id, None)
        _pending_at.pop(user_id, None)
        return None
    return kind


async def _render(message, text: str, markup):
    try:
        return await ui.render(message, text, markup, image=Var.START_PIC)
    except Exception:  # noqa: BLE001
        return await message.reply_text(text, reply_markup=markup,
                                        disable_web_page_preview=True)


# ── main menu ───────────────────────────────────────────────────────────────
def _main_keyboard(values: dict) -> ui.InlineKeyboardMarkup:
    mode = values.get("metadata_mode", "auto")
    thumb = values.get("thumbnail_mode", "anilist")
    rows = [
        [btn(f"🏷 ᴍᴇᴛᴀᴅᴀᴛᴀ · {_MODE_LABEL.get(mode, mode)}", "st_meta",
             raw=True, color=ui.BLUE)],
        [btn(f"🖼 ᴛʜᴜᴍʙɴᴀɪʟ · {_THUMB_LABEL.get(thumb, thumb)}", "st_thumb",
             raw=True, color=ui.BLUE)],
        [btn("✏️ ᴄᴀᴘᴛɪᴏɴ ᴛᴇᴍᴘʟᴀᴛᴇ", "st_caption", color=ui.BLUE)],
        [btn("📁 ꜰɪʟᴇɴᴀᴍᴇ ᴛᴇᴍᴘʟᴀᴛᴇ", "st_filename", color=ui.BLUE)],
        [btn("📝 ꜰɪʟᴇ ᴄᴀᴘᴛɪᴏɴ ᴛᴇᴍᴘʟᴀᴛᴇ", "st_filecap", color=ui.BLUE)],
    ]
    for key, label in TOGGLE_LABELS.items():
        state = "🟢 ᴏɴ" if values.get(key) else "🔴 ᴏꜰꜰ"
        rows.append([btn(f"{label} · {state}", f"st_tgl_{key}", raw=True,
                         color=ui.GREEN if values.get(key) else ui.RED)])
    rows += ui.home_rows(back_data="fd_home", home=False)
    return kb(*rows)


def _main_text(values: dict) -> str:
    return "\n".join([
        bq(f"⚙️ {sc('bot settings')}"),
        bq(sc("encoding and archive extraction are always on.") + "\n"
           + sc("metadata & thumbnail apply to the next leech.")),
        bq(sc("providers") + ": " + ", ".join(esc(s) for s in Var.TORRENT_SITES)),
    ])


async def _show(target):
    values = await settings.all()
    if hasattr(target, "edit_text"):
        await _render(target, _main_text(values), _main_keyboard(values))
    else:
        await target.reply_text(_main_text(values), reply_markup=_main_keyboard(values),
                                disable_web_page_preview=True)


@bot.on_message(filters.command("settings") & filters.private)
async def settings_cmd(client, message):
    await _show(message)


@bot.on_callback_query(filters.regex(r"^st_menu$"))
async def settings_menu(client, query: CallbackQuery):
    await _show(query.message)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^st_tgl_(.+)$"))
async def settings_toggle(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    key = query.matches[0].group(1)
    if key not in TOGGLE_LABELS:
        return await query.answer("Unknown setting.", show_alert=True)
    new_value = await settings.toggle(key)
    await query.answer(f"{TOGGLE_LABELS[key]}: {'ON' if new_value else 'OFF'}")
    await _show(query.message)
    await rep.report(f"Setting '{key}' set to {new_value} by {query.from_user.id}",
                     "info", log=True)


# ── metadata ────────────────────────────────────────────────────────────────
def _meta_keyboard(values: dict, custom: dict) -> ui.InlineKeyboardMarkup:
    mode = values.get("metadata_mode", "auto")
    mode_row = []
    for key in ("auto", "custom", "off"):
        selected = mode == key
        label = f"{'✅ ' if selected else ''}{_MODE_LABEL[key]}"
        mode_row.append(btn(label, f"st_metamode_{key}", raw=True,
                            color=ui.GREEN if selected else ui.BLUE))
    rows = [mode_row]
    for field in CUSTOM_META_FIELDS:
        value = custom.get(field)
        mark = "✅" if value else "•"
        short = (value or "").replace("\n", " ")[:22]
        rows.append([btn(f"{mark} {_FIELD_LABEL[field]}: {short or '—'}",
                         f"st_metafield_{field}", raw=True, color=ui.BLUE)])
    rows.append([btn(BACK, "st_menu", color=ui.BLUE)])
    return kb(*rows)


def _meta_text(values: dict, custom: dict) -> str:
    mode = values.get("metadata_mode", "auto")
    lines = [bq(f"🏷 {sc('metadata')}"),
             bq(sc("current mode") + f": <b>{_MODE_LABEL.get(mode, mode)}</b>"),
             bq(sc("title, audio and subtitles can be set here. leave audio / "
                   "subtitles empty to auto-detect them from the release name."))]
    for field in CUSTOM_META_FIELDS:
        lines.append(bq(f"<b>{_FIELD_LABEL[field]}:</b> {esc(custom.get(field) or '—')}"))
    return "\n".join(lines)


@bot.on_callback_query(filters.regex(r"^st_meta$"))
async def settings_metadata(client, query: CallbackQuery):
    values = await settings.all()
    custom = await settings.get_custom_meta()
    await _render(query.message, _meta_text(values, custom), _meta_keyboard(values, custom))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^st_metamode_(auto|custom|off)$"))
async def settings_meta_mode(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    mode = query.matches[0].group(1)
    await settings.set("metadata_mode", mode)
    values = await settings.all()
    custom = await settings.get_custom_meta()
    await _render(query.message, _meta_text(values, custom), _meta_keyboard(values, custom))
    await query.answer(f"Metadata mode: {_MODE_LABEL[mode]}")


@bot.on_callback_query(filters.regex(r"^st_metafield_(.+)$"))
async def settings_meta_field(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    field = query.matches[0].group(1)
    if field not in CUSTOM_META_FIELDS:
        return await query.answer("Unknown field.", show_alert=True)
    _await(query.from_user.id, f"meta:{field}")
    current = (await settings.get_custom_meta()).get(field, "")
    text = "\n".join([
        bq(f"<b>{_FIELD_LABEL[field]}</b>"),
        bq(sc("send the new value, or send") + " <code>-</code> " + sc("to clear it.")),
        bq(sc("current") + f": <code>{esc(current or '—')}</code>"),
    ])
    await _render(query.message, text, _back("st_meta"))
    await query.answer()


# ── thumbnail ───────────────────────────────────────────────────────────────
def _thumb_keyboard(mode: str) -> ui.InlineKeyboardMarkup:
    rows = []
    for key in ("anilist", "tmdb", "custom", "off"):
        selected = mode == key
        label = f"{'✅ ' if selected else ''}{_THUMB_LABEL[key]}"
        rows.append([btn(label, f"st_thumbmode_{key}", raw=True,
                         color=ui.GREEN if selected else ui.BLUE)])
    if mode == "custom":
        rows.append([btn("📤 ᴜᴘʟᴏᴀᴅ ᴄᴜsᴛᴏᴍ ɪᴍᴀɢᴇ", "st_thumbupload", color=ui.BLUE)])
    rows.append([btn(BACK, "st_menu", color=ui.BLUE)])
    return kb(*rows)


def _thumb_text(mode: str) -> str:
    return "\n".join([
        bq(f"🖼 {sc('thumbnail')}"),
        bq(sc("this image is attached to the uploaded files only.") + "\n"
           + sc("the channel post always uses the fixed 16:9 brand image.")),
        bq(f"{sc('source')}: <b>{_THUMB_LABEL.get(mode, mode)}</b>"),
        bq(sc("anilist · cover art from anilist") + "\n"
           + sc("tmdb · poster from tmdb") + "\n"
           + sc("custom · an image you upload") + "\n"
           + sc("off · no file thumbnail")),
    ])


@bot.on_callback_query(filters.regex(r"^st_thumb$"))
async def settings_thumb(client, query: CallbackQuery):
    mode = await settings.get_thumbnail_mode()
    await _render(query.message, _thumb_text(mode), _thumb_keyboard(mode))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^st_thumbmode_(anilist|tmdb|custom|off)$"))
async def settings_thumb_mode(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    mode = query.matches[0].group(1)
    await settings.set("thumbnail_mode", mode)
    await _render(query.message, _thumb_text(mode), _thumb_keyboard(mode))
    await query.answer(f"Thumbnail: {_THUMB_LABEL[mode]}")


@bot.on_callback_query(filters.regex(r"^st_thumbupload$"))
async def settings_thumb_upload(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    _await(query.from_user.id, "custom_thumb")
    text = "\n".join([
        bq(f"📤 {sc('upload a custom thumbnail')}"),
        bq(sc("send a photo, or an image URL.")),
        bq(sc("current") + ": " + (esc(await settings.get_custom_thumb()) or sc("not set"))),
    ])
    await _render(query.message, text, _back("st_thumb"))
    await query.answer()


# ── caption / filename templates ────────────────────────────────────────────
_PLACEHOLDERS = ("{title} {season} {episode} {year} {quality} {audio} "
                 "{subtitles} {languages} {genres} {plot} {rating} {status} "
                 "{filename} {size} {brand}")


@bot.on_callback_query(filters.regex(r"^st_caption$"))
async def settings_caption(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    current = await settings.get_caption_template() or DEFAULT_TEMPLATE
    _await(query.from_user.id, "caption")
    text = "\n".join([
        bq(f"✏️ {sc('caption template')}"),
        bq(sc("send the new caption template. placeholders") + f":\n<code>{_PLACEHOLDERS}</code>"),
        bq(sc("current") + f":\n<pre>{esc(current)}</pre>"),
    ])
    await _render(query.message, text, _back("st_menu"))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^st_filename$"))
async def settings_filename(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    current = await settings.get_filename_template() or DEFAULT_FILENAME_TEMPLATE
    _await(query.from_user.id, "filename")
    text = "\n".join([
        bq(f"📁 {sc('filename template')}"),
        bq(sc("how uploaded files are named. placeholders") + f":\n<code>{_PLACEHOLDERS}</code>"),
        bq(sc("default") + f":\n<pre>{esc(DEFAULT_FILENAME_TEMPLATE)}</pre>"),
        bq(sc("current") + f":\n<pre>{esc(current)}</pre>"),
    ])
    await _render(query.message, text, _back("st_menu"))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^st_filecap$"))
async def settings_filecap(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    current = await settings.get_file_caption_template() or DEFAULT_FILE_CAPTION
    _await(query.from_user.id, "filecap")
    text = "\n".join([
        bq(f"📝 {sc('file caption template')}"),
        bq(sc("caption attached to the uploaded files. placeholders") + f":\n<code>{_PLACEHOLDERS}</code>"),
        bq(sc("default") + f":\n<pre>{esc(DEFAULT_FILE_CAPTION)}</pre>"),
        bq(sc("current") + f":\n<pre>{esc(current)}</pre>"),
    ])
    await _render(query.message, text, _back("st_menu"))
    await query.answer()


# ── text / photo capture ────────────────────────────────────────────────────
@bot.on_message(filters.private & filters.text, group=-2)
async def settings_capture(client, message: Message):
    pending = _consume(message.from_user.id)
    if not pending:
        raise ContinuePropagation
    if not is_admin(message.from_user.id):
        raise ContinuePropagation

    value = message.text.strip()

    if pending == "caption":
        _pending.pop(message.from_user.id, None)
        await settings.set("caption_template", value)
        return await message.reply_text(
            bq(sc("✅ caption template updated.")), reply_markup=_back("st_menu"))

    if pending == "filename":
        _pending.pop(message.from_user.id, None)
        await settings.set("filename_template", value)
        return await message.reply_text(
            bq(sc("✅ filename template updated.")), reply_markup=_back("st_menu"))

    if pending == "filecap":
        _pending.pop(message.from_user.id, None)
        await settings.set("file_caption_template", value)
        return await message.reply_text(
            bq(sc("✅ file caption template updated.")), reply_markup=_back("st_menu"))

    if pending == "custom_thumb":
        _pending.pop(message.from_user.id, None)
        if value.lower() in ("-", "none", "clear"):
            await settings.set_custom_thumb("")
            return await message.reply_text(
                bq(sc("✅ custom thumbnail cleared.")), reply_markup=_back("st_thumb"))
        await settings.set_custom_thumb(value)
        path = await thumbs.prepare_thumb(value)
        note = (sc("✅ custom thumbnail saved.") if path
                else sc("⚠️ saved, but i could not load that image."))
        return await message.reply_text(bq(note), reply_markup=_back("st_thumb"))

    if pending.startswith("meta:"):
        field = pending.split(":", 1)[1]
        _pending.pop(message.from_user.id, None)
        await settings.set_custom_meta(field, "" if value == "-" else value)
        return await message.reply_text(
            bq(sc("✅ saved") + f" <b>{_FIELD_LABEL.get(field, field)}</b>."),
            reply_markup=_back("st_meta"))

    raise ContinuePropagation


@bot.on_message(filters.private & filters.photo, group=-2)
async def settings_capture_photo(client, message: Message):
    if _pending.get(message.from_user.id) != "custom_thumb":
        raise ContinuePropagation
    _pending.pop(message.from_user.id, None)
    try:
        path = await message.download(file_name="uploaded_thumb.jpg")
        await settings.set_custom_thumb(path or "")
        await thumbs.prepare_thumb(path or "")
        await message.reply_text(bq(sc("✅ custom thumbnail saved.")),
                                 reply_markup=_back("st_thumb"))
    except Exception as exc:  # noqa: BLE001
        rep.report(f"Custom thumbnail upload failed: {exc}", "error", log=True)
        await message.reply_text(bq(sc("⚠️ could not save that photo.")),
                                 reply_markup=_back("st_thumb"))
