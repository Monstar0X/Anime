"""Finder bot UX.

Flow: ``/start`` hub -> filters -> name -> results -> leech (queued).

Every screen is a rich *panel*: a photo header (brand art or the matched
poster) with a styled caption and coloured buttons. Screens edit the same
message in place wherever Telegram allows it, and each one carries a Back /
Home / Close footer so the user never has to run ``/start`` again. A magnet can
be leeched directly, and a running job is cancelled from its own status message.
"""

from __future__ import annotations

from math import ceil

from pyrogram import ContinuePropagation, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, Message

from config import Var, LOGS
from bot.core.bot_instance import bot
from bot.core import ui
from bot.core.ui import CLOSE, NEXT, PREV, bq, btn, esc, kb, sc
from bot.core.search_engine import (
    search_all,
    matches_filters,
    detect_quality,
    quality_label,
    detect_audio,
    group_multi_quality,
    release_key,
)
from bot.core.metadata import resolve as resolve_metadata
from bot.core.leecher import LeechJob, Status
from bot.core.leech_manager import leech_manager
from bot.core.reporter import rep
from bot.core.access import DENY, is_admin

CATEGORIES = ["anime", "series", "movies"]
QUALITIES = ["480", "720", "1080", "HDRip"]

_ICON = {"anime": "🌸", "series": "📺", "movies": "🎬"}
_QUAL_ICON = {"480": "📱", "720": "💽", "1080": "🎞", "HDRip": "💎"}

sessions: dict[int, dict] = {}


# ── session helpers ─────────────────────────────────────────────────────────
def _new_session(uid: int) -> dict:
    sess = {
        "state": "idle",
        "query": "",
        "category": "all",
        "audio": set(),
        "quality": set(),
        "results": [],
        "page": 1,
        "message": None,
        "poster": "",
        "custom": {},
    }
    sessions[uid] = sess
    return sess


def _get(uid: int) -> dict:
    return sessions.get(uid) or _new_session(uid)


def _reset_flow(uid: int):
    """Keep filters, drop results/query and return to the name step."""
    sess = _get(uid)
    sess["query"] = ""
    sess["results"] = []
    sess["page"] = 1
    sess["state"] = "awaiting_name"


def _header(sess: dict) -> str:
    return sess.get("poster") or Var.START_PIC


async def _show(uid: int, message, text: str, markup=None, image=None):
    """Render a panel and remember the (possibly replaced) message."""
    sess = _get(uid)
    msg = await ui.render(message, text, markup, image=image)
    sess["message"] = msg
    return msg


async def _resolve_poster(query: str, category: str) -> str:
    try:
        meta = await resolve_metadata(query, category)
        return meta.poster_url or ""
    except Exception as exc:  # noqa: BLE001 - poster is a nice-to-have
        LOGS.warning(f"[finder] poster lookup failed: {exc}")
        return ""


def _mention(user) -> str:
    return f'<a href="tg://user?id={user.id}">{esc(user.first_name or "there")}</a>'


# ── keyboards ───────────────────────────────────────────────────────────────
def _category_row(sess: dict) -> list[InlineKeyboardButton]:
    row = [btn("🌐 ᴀʟʟ", "fd_cat_all",
               color=ui.GREEN if sess["category"] == "all" else ui.BLUE)]
    for cat in CATEGORIES:
        selected = sess["category"] == cat
        row.append(btn(f"{'✅ ' if selected else ''}{_ICON[cat]} {cat.title()}",
                       f"fd_cat_{cat}", raw=True,
                       color=ui.GREEN if selected else ui.BLUE))
    return row


def _quality_row(sess: dict) -> list[InlineKeyboardButton]:
    row = [btn("🌐 ᴀʟʟ", "fd_q_all",
               color=ui.GREEN if not sess["quality"] else ui.BLUE)]
    for qual in QUALITIES:
        selected = qual in sess["quality"]
        row.append(btn(f"{'✅ ' if selected else ''}{_QUAL_ICON[qual]} {qual}",
                       f"fd_q_{qual}", raw=True,
                       color=ui.GREEN if selected else ui.BLUE))
    return row


def _filter_rows(sess: dict) -> list[list[InlineKeyboardButton]]:
    return [_category_row(sess), _quality_row(sess)]


def _filter_text(sess: dict, name_step: bool) -> str:
    tail = (sc("tap") + f" <b>{sc('next')}</b> " + sc("when done, then send the name.")
            if name_step else
            sc("pick a category and/or quality, then tap")
            + f" <b>{sc('search')}</b>.")
    return "\n".join([
        bq(f"🎚 {sc('choose filters')}"),
        bq(sc("type") + ": " + sc("anime / series / movies") + "\n"
           + sc("quality") + ": " + sc("480p · 720p · 1080p · hdrip")),
        bq(sc("audio / subtitles are shown in the post caption — you can also "
              "type them in the name, e.g.") + " <code>one piece hindi</code>."),
        bq(sc("nothing selected = search everything.") + "\n" + tail),
        bq(f"🎚 {_chips(sess)}"),
    ])


def _prefilter_keyboard(sess: dict) -> ui.InlineKeyboardMarkup:
    rows = _filter_rows(sess)
    rows.append([btn("➡️ ɴᴇxᴛ", "fd_next", color=ui.GREEN),
                 btn("🧲 ᴍᴀɢɴᴇᴛ", "fd_magnet", color=ui.BLUE)])
    rows += ui.home_rows(back_data="fd_home", home=False)
    return kb(*rows)


def _filter_keyboard(sess: dict) -> ui.InlineKeyboardMarkup:
    rows = _filter_rows(sess)
    rows.append([btn("🔎 ꜱᴇᴀʀᴄʜ", "fd_search", color=ui.GREEN),
                 btn("✍️ ɴᴇᴡ ɴᴀᴍᴇ", "fd_name", color=ui.BLUE)])
    rows += ui.home_rows(back_data="fd_start")
    return kb(*rows)


def _results_keyboard(sess: dict, filtered: list) -> ui.InlineKeyboardMarkup:
    per_page = Var.RESULTS_PER_PAGE
    start = (sess["page"] - 1) * per_page
    page_items = filtered[start:start + per_page]

    rows: list[list[InlineKeyboardButton]] = []
    for offset, res in enumerate(page_items):
        idx = start + offset
        qual = quality_label(detect_quality(res.title))
        badge = f"{_QUAL_ICON.get(qual, '🎬')} " if qual else ""
        label = f"{idx + 1}. {badge}{res.display_name}"
        rows.append([btn(label[:60], f"fd_sel_{idx}", raw=True, color=ui.BLUE)])

    nav = []
    if sess["page"] > 1:
        nav.append(btn(PREV, f"fd_page_{sess['page'] - 1}", color=ui.BLUE))
    total_pages = max(1, ceil(len(filtered) / per_page))
    if total_pages > 1:
        nav.append(btn(f"· {sess['page']}/{total_pages} ·", "fd_noop", raw=True))
    if start + per_page < len(filtered):
        nav.append(btn(NEXT, f"fd_page_{sess['page'] + 1}", color=ui.BLUE))
    if nav:
        rows.append(nav)

    rows.append([btn("🎚 ꜰɪʟᴛᴇʀꜱ", "fd_filters", color=ui.BLUE),
                 btn("🔄 ꜱᴇᴀʀᴄʜ ᴀɢᴀɪɴ", "fd_name", color=ui.GREEN)])
    rows.append([btn("🧲 ᴍᴀɢɴᴇᴛ", "fd_magnet", color=ui.BLUE)])
    rows += ui.home_rows(back_data="fd_filters")
    return kb(*rows)


# ── text builders ───────────────────────────────────────────────────────────
def _chips(sess: dict) -> str:
    bits = []
    if sess["category"] != "all":
        bits.append(f"{_ICON.get(sess['category'], '🎬')} {sess['category'].title()}")
    bits += [f"{_QUAL_ICON[q]} {q}" for q in QUALITIES if q in sess["quality"]]
    return " · ".join(bits) if bits else sc("no filters · showing everything")


def _result_line(idx: int, res) -> str:
    qual = quality_label(detect_quality(res.title)) or "?"
    tags = detect_audio(res.title) - {"unknown"}
    audio = "/".join(sorted(t.title() for t in tags)) if tags else "?"
    return (f"<b>{idx}.</b> {esc(res.display_name[:70])}\n"
            f"   <code>{_QUAL_ICON.get(qual, '🎬')} {qual} · 🎧 {audio} · "
            f"💾 {ui.human(res.size_bytes)} · ⬆ {res.seeders} · {esc(res.provider)}</code>")


def _format_results(sess: dict, filtered: list) -> str:
    per_page = Var.RESULTS_PER_PAGE
    start = (sess["page"] - 1) * per_page
    page_items = filtered[start:start + per_page]

    lines = [bq(f"🔍 {sc('results for')} “{esc(sess['query'])}” · <b>{len(filtered)}</b>")]
    lines.append(bq(f"🎚 {_chips(sess)}"))
    for offset, res in enumerate(page_items):
        lines.append(bq(_result_line(start + offset + 1, res)))
    lines.append(f"<i>{sc('tap a number below, or reply with it to leech')}.</i>")
    return "\n".join(lines)


def _hub_text(user) -> str:
    return "\n".join([
        bq(f"👋 {sc('hey')} {_mention(user)}!"),
        bq(sc("i find, leech and post any") + "\n"
           + sc("🌸 anime   📺 series   🎬 movies") + "\n\n"
           + sc("pick your filters, type a name and i will search every provider, "
                "then publish download buttons by quality.")),
        bq(sc("tap the button below to begin 👇")),
    ])


def _hub_keyboard() -> ui.InlineKeyboardMarkup:
    return kb(
        [btn("🔍 ꜰɪɴᴅ ʜᴇʀᴇ", "fd_start", color=ui.GREEN)],
        [btn("⚙️ ꜱᴇᴛᴛɪɴɢꜱ", "st_menu", color=ui.BLUE),
         btn("ℹ️ ᴀʙᴏᴜᴛ", "fd_about", color=ui.BLUE)],
        [btn("📖 ʜᴇʟᴘ", "fd_help", color=ui.BLUE),
         btn(CLOSE, "close", color=ui.RED)],
    )


def _about_text() -> str:
    return "\n".join([
        bq(f"🌸 {sc('about this bot')}"),
        bq(sc("a multi-provider torrent finder, leecher and poster.") + "\n"
           + sc("search anime, series and movies; it detects quality, audio and "
                "subtitles, resolves metadata, downloads, extracts archives and "
                "publishes download buttons.")),
        bq(sc("providers") + ": " + ", ".join(esc(s) for s in Var.TORRENT_SITES)),
    ])


def _help_text() -> str:
    cmds = [
        ("/start", "open the search hub"),
        ("/settings", "toggles for metadata, thumbnail, encoding…"),
        ("/help", "this message"),
        ("/about", "about the bot"),
    ]
    body = "\n".join(f"<code>{c}</code> ➜ {sc(d)}" for c, d in cmds)
    return "\n".join([
        bq(f"📖 {sc('everything i can do')}"),
        bq(body),
        bq(sc("tip · no command needed — tap") + f" <b>{sc('find here')}</b> "
           + sc("and send a name.")),
    ])


# ── filters ─────────────────────────────────────────────────────────────────
def _apply_filters(sess: dict) -> list:
    cats = set() if sess["category"] == "all" else {sess["category"]}
    quality = set(sess["quality"])
    return [r for r in sess["results"]
            if matches_filters(r, cats, set(), quality)]


# ── screens ─────────────────────────────────────────────────────────────────
async def _show_hub(uid: int, message, user=None):
    _get(uid)["state"] = "idle"
    user = user or message.from_user
    await _show(uid, message, _hub_text(user), _hub_keyboard(), image=Var.START_PIC)


async def _show_name(uid: int, message):
    sess = _get(uid)
    sess["state"] = "awaiting_name"
    text = "\n".join([
        bq(f"✍️ {sc('send me the name')}"),
        bq(sc("of the anime / series / movie.") + "\n"
           + sc("a short description works too, e.g.") + " "
           + "<code>one piece 1080p</code>"),
        bq(sc("or tap 🧲 magnet to paste a link.")),
    ])
    markup = kb(
        [btn("🧲 ᴍᴀɢɴᴇᴛ", "fd_magnet", color=ui.BLUE)],
        *ui.home_rows(back_data="fd_start"),
    )
    await _show(uid, message, text, markup, image=_header(sess))


async def _show_filters(uid: int, message):
    sess = _get(uid)
    sess["state"] = "awaiting_filter"
    await _show(uid, message, _filter_text(sess, name_step=False),
                _filter_keyboard(sess), image=_header(sess))


async def _show_results(uid: int, message):
    sess = _get(uid)
    filtered = _apply_filters(sess)
    sess["state"] = "awaiting_selection"
    if not filtered:
        text = "\n".join([
            bq(f"😕 {sc('no results matched your filters for')} “{esc(sess['query'])}”"),
            bq(sc("widen the filters, or search another name.")),
        ])
        markup = kb(
            [btn("🎚 ꜰɪʟᴛᴇʀꜱ", "fd_filters", color=ui.BLUE),
             btn("✍️ ɴᴇᴡ ɴᴀᴍᴇ", "fd_name", color=ui.GREEN)],
            *ui.home_rows(back_data="fd_filters"),
        )
        await _show(uid, message, text, markup, image=_header(sess))
        return

    text = _format_results(sess, filtered)
    # Photo captions cap at 1024 chars; fall back to a text panel when long.
    image = _header(sess) if len(text) <= 1000 else None
    await _show(uid, message, text, _results_keyboard(sess, filtered), image=image)


async def _run_search(uid: int, message):
    sess = _get(uid)
    await _show(uid, message,
                bq(sc("🔎 searching for") + f" “{esc(sess['query'])}”…"),
                image=_header(sess))
    category = "all" if sess["category"] == "all" else sess["category"]
    outcome = await search_all(sess["query"], category=category)
    sess["results"] = outcome.results
    sess["page"] = 1
    sess["poster"] = await _resolve_poster(sess["query"], category)
    if not outcome.results:
        used = ", ".join(outcome.providers_used) or sc("no provider")
        sess["state"] = "awaiting_name"
        text = "\n".join([
            bq(f"😕 {sc('nothing found for')} “{esc(sess['query'])}”"),
            bq(sc("searched") + f": {esc(used)}"),
            bq(sc("send another name to try again — no need to /start.")),
        ])
        markup = kb(
            [btn("✍️ ɴᴇᴡ ɴᴀᴍᴇ", "fd_name", color=ui.GREEN),
             btn("🎚 ꜰɪʟᴛᴇʀꜱ", "fd_filters", color=ui.BLUE)],
            *ui.home_rows(back_data="fd_home"),
        )
        await _show(uid, message, text, markup, image=_header(sess))
        return
    await _show_results(uid, message)


# ── leech ───────────────────────────────────────────────────────────────────
class _MagnetResult:
    """Minimal TorrentResult-like object for a raw magnet link."""

    def __init__(self, title: str, magnet: str):
        self.title = title
        self.magnet = magnet
        self.provider = "magnet"
        self.size_bytes = 0
        self.seeders = 0
        self.category_hint = ""

    @property
    def display_name(self) -> str:
        return self.title


async def _start_leech(uid: int, idx: int, filtered: list, reply_to: Message):
    sess = _get(uid)
    primary = filtered[idx]
    siblings = group_multi_quality(sess["results"]).get(release_key(primary), [])
    siblings = [s for s in siblings if s is not primary]

    status_msg = await reply_to.reply_text(
        bq(f"‣ <b>{esc(primary.display_name)}</b>") + "\n" + bq(sc("queueing…")))
    status = Status(status_msg, title=primary.display_name)
    job = LeechJob(
        query=sess["query"],
        category="all" if sess["category"] == "all" else sess["category"],
        primary=primary,
        siblings=siblings,
        user_id=uid,
        custom_meta=dict(sess.get("custom") or {}),
    )
    item = await leech_manager.submit(job, status)
    status.cancel_id = item.id
    if leech_manager.running() is not None and leech_manager.running().id != item.id:
        await status.update(
            bq(f"‣ <b>{esc(primary.display_name)}</b>") + "\n"
            + bq(sc("queued — position") + f" {item.position}"), force=True)
    await rep.report(f"Leech queued by {uid}: {primary.title}", "info", log=True)


async def _start_magnet_leech(uid: int, magnet: str, reply_to: Message):
    sess = _get(uid)
    name = magnet.split("&dn=")[-1].split("&")[0].replace("+", " ") or "Magnet"
    status_msg = await reply_to.reply_text(
        bq(f"‣ <b>{esc(name[:80])}</b>") + "\n" + bq(sc("queueing magnet…")))
    status = Status(status_msg, title=name[:80])
    job = LeechJob(
        query=sess.get("query") or name,
        category="all",
        primary=_MagnetResult(name, magnet),
        siblings=[],
        user_id=uid,
        custom_meta=dict(sess.get("custom") or {}),
    )
    item = await leech_manager.submit(job, status)
    status.cancel_id = item.id
    await rep.report(f"Magnet leech queued by {uid}", "info", log=True)


# ── command / callback handlers ─────────────────────────────────────────────
@bot.on_message(filters.command("start") & filters.private)
async def finder_start(client, message: Message):
    # Deep links (download buttons) carry a payload and are served by
    # bot/plugins/start.py; let it handle those.
    if len(message.text.split()) > 1:
        raise ContinuePropagation
    uid = message.from_user.id
    _new_session(uid)
    await _show_hub(uid, message)


@bot.on_message(filters.command("about") & filters.private)
async def finder_about_cmd(client, message: Message):
    _new_session(message.from_user.id)
    await _show(message.from_user.id, message, _about_text(),
                kb(*ui.home_rows(back_data="fd_home", home=False)), image=Var.START_PIC)


@bot.on_message(filters.command("help") & filters.private)
async def finder_help_cmd(client, message: Message):
    _new_session(message.from_user.id)
    await _show(message.from_user.id, message, _help_text(),
                kb(*ui.home_rows(back_data="fd_home", home=False)), image=Var.START_PIC)


@bot.on_callback_query(filters.regex(r"^fd_home$"))
async def finder_home(client, query: CallbackQuery):
    await _show_hub(query.from_user.id, query.message, user=query.from_user)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_about$"))
async def finder_about(client, query: CallbackQuery):
    await _show(query.from_user.id, query.message, _about_text(),
                kb(*ui.home_rows(back_data="fd_home", home=False)), image=Var.START_PIC)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_help$"))
async def finder_help(client, query: CallbackQuery):
    await _show(query.from_user.id, query.message, _help_text(),
                kb(*ui.home_rows(back_data="fd_home", home=False)), image=Var.START_PIC)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_start$"))
async def finder_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    if not is_admin(uid):
        return await query.answer(DENY, show_alert=True)
    sess = sessions.get(uid)
    if not sess or sess["state"] not in ("awaiting_prefilter", "awaiting_name",
                                         "awaiting_filter", "awaiting_selection"):
        sess = _new_session(uid)
    sess["state"] = "awaiting_prefilter"
    await _show(uid, query.message, _filter_text(sess, name_step=True),
                _prefilter_keyboard(sess), image=_header(sess))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_name$"))
async def finder_name(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    _reset_flow(query.from_user.id)
    await _show_name(query.from_user.id, query.message)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_magnet$"))
async def finder_magnet(client, query: CallbackQuery):
    uid = query.from_user.id
    if not is_admin(uid):
        return await query.answer(DENY, show_alert=True)
    sess = _get(uid)
    sess["state"] = "awaiting_magnet"
    text = "\n".join([
        bq(f"🧲 {sc('send a magnet link')}"),
        bq("<code>magnet:?xt=urn:btih:…</code>"),
        bq(sc("i'll leech it, extract any archives and post it with download buttons.")),
    ])
    await _show(uid, query.message, text, kb(*ui.home_rows(back_data="fd_name")),
                image=_header(sess))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_filters$"))
async def finder_show_filters(client, query: CallbackQuery):
    await _show_filters(query.from_user.id, query.message)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_search$"))
async def finder_do_search(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    await query.answer(sc("searching…"))
    await _run_search(query.from_user.id, query.message)


@bot.on_callback_query(filters.regex(r"^fd_next$"))
async def finder_next(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    await _show_name(query.from_user.id, query.message)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_noop$"))
async def finder_noop(client, query: CallbackQuery):
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_page_(\d+)$"))
async def finder_page(client, query: CallbackQuery):
    sess = _get(query.from_user.id)
    sess["page"] = int(query.matches[0].group(1))
    await _show_results(query.from_user.id, query.message)
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_sel_(\d+)$"))
async def finder_select(client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer(DENY, show_alert=True)
    sess = _get(query.from_user.id)
    idx = int(query.matches[0].group(1))
    filtered = _apply_filters(sess)
    if not (0 <= idx < len(filtered)):
        return await query.answer(sc("result expired, search again."), show_alert=True)
    await query.answer(sc("starting leech…"))
    await _start_leech(query.from_user.id, idx, filtered, query.message)


@bot.on_callback_query(filters.regex(r"^fd_(cat|q)_(.+)$"))
async def finder_toggle(client, query: CallbackQuery):
    kind, value = query.matches[0].group(1), query.matches[0].group(2)
    sess = _get(query.from_user.id)

    if kind == "cat":
        sess["category"] = "all" if value == "all" else value
    elif kind == "q":
        if value == "all":
            sess["quality"].clear()
        elif value in sess["quality"]:
            sess["quality"].discard(value)
        else:
            sess["quality"].add(value)

    if sess["state"] == "awaiting_filter":
        await _show_filters(query.from_user.id, query.message)
    else:
        sess["state"] = "awaiting_prefilter"
        await _show(query.from_user.id, query.message, _filter_text(sess, name_step=True),
                    _prefilter_keyboard(sess), image=_header(sess))
    await query.answer()


@bot.on_callback_query(filters.regex(r"^fd_cancel_(\d+)$"))
async def finder_cancel(client, query: CallbackQuery):
    tid = int(query.matches[0].group(1))
    item = leech_manager.cancel(tid)
    if not item:
        return await query.answer(sc("already finished."), show_alert=True)
    running = leech_manager.running()
    if running and running.id == tid:
        await query.answer(sc("cancelling…"))
    else:
        await query.answer(sc("removed from queue."))


# ── free-text listener ──────────────────────────────────────────────────────
@bot.on_message(filters.private & filters.text & ~filters.command(
    ["start", "help", "about", "settings", "post", "search", "ping"]), group=-1)
async def finder_text(client, message: Message):
    uid = message.from_user.id
    sess = sessions.get(uid)
    if not sess:
        raise ContinuePropagation

    state = sess["state"]

    if state in ("awaiting_name", "awaiting_magnet", "awaiting_prefilter",
                 "awaiting_filter", "awaiting_selection") and not is_admin(uid):
        return await message.reply_text(bq(sc(DENY)))

    if state == "awaiting_name":
        text = message.text.strip()
        if text.lower().startswith("magnet:"):
            prompt = await message.reply_text(bq(sc("🧲 queueing magnet…")))
            sess["message"] = prompt
            await _start_magnet_leech(uid, text, prompt)
            return
        if not text:
            await message.reply_text(sc("✍️ please send a name."))
            return
        sess["query"] = text
        prompt = await message.reply_text(bq(sc("⏳ searching…")))
        sess["message"] = prompt
        await _run_search(uid, prompt)
        return

    if state == "awaiting_magnet":
        text = message.text.strip()
        if not text.lower().startswith("magnet:"):
            await message.reply_text(
                bq(sc("❌ that doesn't look like a magnet link.")) + "\n"
                + sc("send one starting with") + " <code>magnet:?xt=urn:btih:</code>")
            return
        prompt = await message.reply_text(bq(sc("🧲 queueing magnet…")))
        sess["message"] = prompt
        await _start_magnet_leech(uid, text, prompt)
        return

    if state in ("awaiting_prefilter", "awaiting_filter"):
        # Typing a name on a filter screen searches it directly.
        text = message.text.strip()
        if not text:
            raise ContinuePropagation
        sess["query"] = text
        prompt = await message.reply_text(bq(sc("⏳ searching…")))
        sess["message"] = prompt
        await _run_search(uid, prompt)
        return

    if state == "awaiting_selection":
        text = message.text.strip()
        if not text.isdigit():
            raise ContinuePropagation
        idx = int(text) - 1
        filtered = _apply_filters(sess)
        if 0 <= idx < len(filtered):
            await _start_leech(uid, idx, filtered, message)
        else:
            await message.reply_text(bq(sc("❌ that number is out of range.")))
        return

    raise ContinuePropagation
