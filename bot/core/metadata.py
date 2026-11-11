"""Resolve rich metadata (title, plot, poster, year...) for a search query.

Anime  -> AniList GraphQL (no key required)
Movie/Series -> TMDB (requires ``TMDB_API_KEY``)
Fallback -> parse the torrent release name with anitopy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from aiohttp import ClientSession
from anitopy import parse as anitopy_parse

from config import Var, LOGS

_ANILIST_API = "https://graphql.anilist.co"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AutoAnimeBot/1.0)",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://anilist.co",
    "Referer": "https://anilist.co/",
}

_ANILIST_QUERY = """
query ($search: String, $type: MediaType) {
  Media(search: $search, type: $type) {
    id
    idMal
    title { romaji english native }
    description(asHtml: false)
    startDate { year month day }
    averageScore
    status(version: 2)
    genres
    coverImage { extraLarge large }
    bannerImage
    episodes
    seasonYear
  }
}
"""


@dataclass
class Metadata:
    title: str = ""
    season: str = ""
    episode: str = ""
    year: str = ""
    genres: list[str] = field(default_factory=list)
    plot: str = ""
    rating: str = ""
    status: str = ""
    poster_url: str = ""
    banner_url: str = ""
    backdrop_url: str = ""
    imdb_id: str = ""
    audio: str = ""
    subtitles: str = ""
    source: str = "filename"
    raw: dict = field(default_factory=dict)


def _from_filename(name: str) -> Metadata:
    parsed = anitopy_parse(name) or {}
    title = parsed.get("anime_title") or name
    return Metadata(
        title=str(title).strip(),
        season=str(parsed.get("anime_season", "") or ""),
        episode=str(parsed.get("episode_number", "") or ""),
        year=str(parsed.get("anime_year", "") or ""),
        source="filename",
    )


async def _anilist(query: str) -> Metadata | None:
    try:
        async with ClientSession(headers=_HEADERS) as session:
            async with session.post(
                _ANILIST_API,
                json={"query": _ANILIST_QUERY,
                      "variables": {"search": query, "type": "ANIME"}},
                timeout=20,
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[metadata] AniList failed: {exc}")
        return None

    media = (payload.get("data") or {}).get("Media")
    if not media:
        return None

    titles = media.get("title") or {}
    sd = media.get("startDate") or {}
    desc = media.get("description") or ""
    desc = desc.replace("<br>", "\n").replace("<i>", "").replace("</i>", "")

    return Metadata(
        title=(titles.get("english") or titles.get("romaji") or titles.get("native") or query),
        year=str(sd.get("year") or media.get("seasonYear") or ""),
        genres=media.get("genres") or [],
        plot=desc.strip(),
        rating=(f"{media.get('averageScore')}%" if media.get("averageScore") else ""),
        status=str(media.get("status") or "").replace("_", " ").title(),
        poster_url=((media.get("coverImage") or {}).get("extraLarge")
                    or (media.get("coverImage") or {}).get("large") or ""),
        banner_url=(media.get("bannerImage") or ""),
        source="anilist",
        raw=media,
    )


async def anilist_cover(query: str) -> str:
    """Return just the AniList cover URL for ``query`` (used for thumbnails)."""
    meta = await _anilist(query)
    return meta.poster_url if meta else ""


async def _tmdb(query: str, category: str) -> Metadata | None:
    if not Var.TMDB_API_KEY:
        return None
    kind = "movie" if category == "movies" else "tv"
    try:
        async with ClientSession() as session:
            async with session.get(
                f"https://api.themoviedb.org/3/search/{kind}",
                params={"api_key": Var.TMDB_API_KEY, "query": query},
                timeout=20,
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[metadata] TMDB failed: {exc}")
        return None

    hits = payload.get("results") or []
    if not hits:
        return None
    hit = hits[0]

    date = hit.get("release_date") or hit.get("first_air_date") or ""
    return Metadata(
        title=hit.get("title") or hit.get("name") or query,
        year=date[:4],
        genres=[],
        plot=(hit.get("overview") or "").strip(),
        rating=(f"{round(hit.get('vote_average', 0), 1)}/10"
                if hit.get("vote_average") else ""),
        poster_url=(f"https://image.tmdb.org/t/p/w500{hit['poster_path']}"
                    if hit.get("poster_path") else ""),
        backdrop_url=(f"https://image.tmdb.org/t/p/w1280{hit['backdrop_path']}"
                      if hit.get("backdrop_path") else ""),
        source="tmdb",
        raw=hit,
    )


async def resolve(query: str, category: str = "all", name_hint: str = "",
                  custom: dict | None = None) -> Metadata:
    """Return the best metadata available for ``query``.

    ``name_hint`` is an optional torrent release name used to enrich the
    result with season / episode information.  ``custom`` holds user-supplied
    field overrides (title, plot, poster_url, …) which always win.
    """
    custom = custom or {}
    order = ["anime", "series", "movies"] if category in ("all", "") else [category]

    meta: Metadata | None = None
    for cat in order:
        if cat == "anime":
            meta = await _anilist(query)
        else:
            meta = await _tmdb(query, cat)
        if meta:
            break

    # The raw query is often a messy release string ("one piece 1100 dual");
    # retry with the clean parsed title so plot/poster are actually found.
    if meta is None and name_hint:
        clean = str((anitopy_parse(name_hint) or {}).get("anime_title") or "").strip()
        if clean and clean.lower() != query.lower():
            for cat in order:
                meta = await (_anilist(clean) if cat == "anime" else _tmdb(clean, cat))
                if meta:
                    break

    if meta is None:
        meta = _from_filename(name_hint or query)

    if name_hint:
        parsed = anitopy_parse(name_hint) or {}
        meta.season = meta.season or str(parsed.get("anime_season", "") or "")
        meta.episode = meta.episode or str(parsed.get("episode_number", "") or "")
        if not meta.year:
            meta.year = str(parsed.get("anime_year", "") or "")

    meta.title = meta.title or query
    meta.plot = (meta.plot or "")[:400]

    if custom:
        meta = apply_custom(meta, custom, query)
    return meta


def apply_custom(meta: Metadata, custom: dict, query: str = "") -> Metadata:
    """Overlay user-supplied fields on top of ``meta`` (custom wins)."""
    if not custom:
        return meta
    if custom.get("title"):
        meta.title = custom["title"]
    for field in ("season", "episode", "year", "plot", "rating", "status",
                  "poster_url", "audio", "subtitles"):
        if custom.get(field):
            setattr(meta, field, custom[field])
    if custom.get("genres"):
        raw = custom["genres"]
        meta.genres = [g.strip() for g in raw.split(",") if g.strip()] \
            if isinstance(raw, str) else list(raw)
    meta.source = "custom"
    return meta


def custom_only(query: str, custom: dict) -> Metadata:
    """Build metadata purely from user input (metadata mode = custom)."""
    meta = Metadata(title=custom.get("title") or query, source="custom")
    return apply_custom(meta, custom, query)
