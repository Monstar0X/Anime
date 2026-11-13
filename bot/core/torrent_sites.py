"""Torrent provider abstraction.

Every provider returns a list of :class:`TorrentResult`.  New providers can be
added either in code (subclass :class:`TorrentSite` and register it) or, without
touching code, through ``custom_sites.json`` (see ``custom_sites.example.json``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from os import path as ospath
from typing import Iterable
from urllib.parse import quote_plus, urlencode

from aiohttp import ClientError, ClientSession

from config import Var, LOGS

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
]

_SIZE_UNITS = {
    "b": 1,
    "kb": 1024,
    "kib": 1024,
    "mb": 1024 ** 2,
    "mib": 1024 ** 2,
    "gb": 1024 ** 3,
    "gib": 1024 ** 3,
    "tb": 1024 ** 4,
    "tib": 1024 ** 4,
}


@dataclass
class TorrentResult:
    title: str
    magnet: str
    provider: str
    size_bytes: int = 0
    seeders: int = 0
    leechers: int = 0
    category_hint: str = ""
    pub_date: str = ""
    page_url: str = ""
    quality_hint: str = ""
    info_hash: str = ""
    score: float = 0.0
    extra: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return re.sub(r"\s+", " ", self.title).strip()


def parse_size(text) -> int:
    """Parse a provider size as bytes.

    Providers disagree on representation: some send `1.4 GiB`, others send
    a raw byte count as an integer or numeric string.
    """
    if text is None or text == "":
        return 0
    if isinstance(text, (int, float)):
        return max(0, int(text))
    value_text = str(text).strip().replace(",", "")
    if not value_text:
        return 0
    # Bare numeric values in these provider APIs are byte counts.
    if re.fullmatch(r"\d+(?:\.\d+)?", value_text):
        try:
            return max(0, int(float(value_text)))
        except ValueError:
            return 0
    m = re.search(r"([\d.]+)\s*([KMGT]?i?B)\b", value_text, re.IGNORECASE)
    if not m:
        return 0
    try:
        amount = float(m.group(1))
    except ValueError:
        return 0
    return max(0, int(amount * _SIZE_UNITS.get(m.group(2).lower(), 1)))


def parse_int(text) -> int:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return 0


def build_magnet(info_hash: str, name: str = "") -> str:
    if not info_hash:
        return ""
    base = f"magnet:?xt=urn:btih:{info_hash}"
    if name:
        base += f"&dn={quote_plus(name)}"
    for tracker in TRACKERS:
        base += f"&tr={quote_plus(tracker)}"
    return base


def _extract_magnet(*texts: str) -> str:
    for text in texts:
        if not text:
            continue
        m = re.search(r"magnet:\?[^\"'<>\s]+", text)
        if m:
            return m.group(0)
    return ""


class ProviderRequestError(RuntimeError):
    """A provider could not be reached or rejected the request."""


async def _get(url: str, *, params: dict | None = None, timeout: int = 15,
               headers: dict | None = None) -> str:
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    try:
        async with ClientSession(headers=hdrs) as session:
            async with session.get(url, params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    detail = f"HTTP {resp.status}"
                    LOGS.warning(f"[torrent_sites] {url} -> {detail}")
                    raise ProviderRequestError(detail)
                return await resp.text()
    except ProviderRequestError:
        raise
    except (ClientError, TimeoutError, OSError) as exc:
        LOGS.warning(f"[torrent_sites] {url} failed: {exc}")
        raise ProviderRequestError(str(exc)) from exc


class TorrentSite:
    id = "base"
    label = "Base"

    def categories(self) -> Iterable[str]:
        return ("anime", "series", "movies")

    async def search(self, query: str, category: str = "all") -> list[TorrentResult]:
        raise NotImplementedError

    # convenience -----------------------------------------------------------------
    def make_result(self, **kwargs) -> TorrentResult:
        kwargs.setdefault("provider", self.id)
        return TorrentResult(**kwargs)


class NyaaSite(TorrentSite):
    id = "nyaa"
    label = "Nyaa"

    _CAT = {"anime": "1_0", "series": "4_0", "movies": "4_0"}

    async def search(self, query, category="all"):
        params = {"page": "rss", "q": query, "f": "0"}
        cat = self._CAT.get(category)
        if cat:
            params["c"] = cat
        text = await _get("https://nyaa.si/", params=params)
        if not text:
            return []
        return self._parse_rss(text)

    @staticmethod
    def _parse_rss(text: str) -> list[TorrentResult]:
        import feedparser

        feed = feedparser.parse(text)
        out: list[TorrentResult] = []
        for entry in feed.entries:
            info_hash = (entry.get("nyaa_infohash") or "").strip()
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            out.append(TorrentResult(
                title=title,
                magnet=build_magnet(info_hash, title),
                provider="nyaa",
                size_bytes=parse_size(entry.get("nyaa_size", "")),
                seeders=parse_int(entry.get("nyaa_seeders")),
                leechers=parse_int(entry.get("nyaa_leechers")),
                category_hint=(entry.get("nyaa_category") or "").lower(),
                pub_date=entry.get("published", ""),
                page_url=entry.get("guid", "") or link,
                info_hash=info_hash,
            ))
        return out


class SubsPleaseSite(TorrentSite):
    id = "subsplease"
    label = "SubsPlease"

    def categories(self):
        return ("anime",)

    async def search(self, query, category="all"):
        if category not in ("all", "anime"):
            return []
        text = await _get(
            "https://subsplease.org/api/",
            params={"f": "search", "tz": "UTC", "s": query},
        )
        if not text:
            return []
        try:
            data = json.loads(text)
        except ValueError:
            return []
        out: list[TorrentResult] = []
        for name, item in (data or {}).items():
            if not isinstance(item, dict):
                continue
            for dl in item.get("downloads", []):
                res = str(dl.get("res", "")).strip()
                out.append(TorrentResult(
                    title=name if not res else f"{name} ({res}p)",
                    magnet=dl.get("magnet", ""),
                    provider="subsplease",
                    size_bytes=parse_size(dl.get("size", "")),
                    category_hint="anime",
                    pub_date=item.get("release_date", ""),
                    quality_hint=res,
                ))
        return out


class ApibaySite(TorrentSite):
    """The Pirate Bay via the public apibay.org mirror."""

    id = "apibay"
    label = "The Pirate Bay"

    async def search(self, query, category="all"):
        text = await _get("https://apibay.org/q.php", params={"q": query})
        if not text:
            return []
        try:
            data = json.loads(text)
        except ValueError:
            return []
        out: list[TorrentResult] = []
        for item in data or []:
            info_hash = (item.get("info_hash") or "").upper()
            name = item.get("name") or ""
            if not info_hash or name.lower() == "no results returned":
                continue
            out.append(TorrentResult(
                title=name,
                magnet=build_magnet(info_hash, name),
                provider="apibay",
                size_bytes=parse_int(item.get("size")),
                seeders=parse_int(item.get("seeders")),
                leechers=parse_int(item.get("leechers")),
                info_hash=info_hash,
                extra={"imdb": item.get("imdb", ""), "category": item.get("category", "")},
            ))
        return out


async def _tmdb_tv_imdb_id(query: str) -> str:
    """Resolve a TV title to its IMDb id for EZTV's supported lookup API."""
    if not Var.TMDB_API_KEY:
        return ""
    try:
        async with ClientSession(headers={"User-Agent": UA, "Accept": "application/json"}) as session:
            async with session.get(
                "https://api.themoviedb.org/3/search/tv",
                params={"api_key": Var.TMDB_API_KEY, "query": query},
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    raise ProviderRequestError(f"TMDB TV search HTTP {resp.status}")
                payload = await resp.json()
            hits = (payload or {}).get("results") or []
            if not hits:
                return ""
            # TMDB search is relevance-ranked; use its first result.
            tv_id = hits[0].get("id")
            if not tv_id:
                return ""
            async with session.get(
                f"https://api.themoviedb.org/3/tv/{tv_id}/external_ids",
                params={"api_key": Var.TMDB_API_KEY},
                timeout=15,
            ) as resp:
                if resp.status != 200:
                    raise ProviderRequestError(f"TMDB external IDs HTTP {resp.status}")
                ids = await resp.json()
            return str((ids or {}).get("imdb_id") or "")
    except Exception as exc:  # noqa: BLE001
        LOGS.warning(f"[torrent_sites] TMDB IMDb lookup failed for {query!r}: {exc}")
        return ""


class EztvSite(TorrentSite):
    id = "eztv"
    label = "EZTV"

    def categories(self):
        return ("series",)

    async def search(self, query, category="all"):
        if category not in ("all", "series"):
            return []

        # EZTV's API does not offer a title query parameter. Its supported
        # show-specific lookup is IMDb-ID based; searching only page 1 of the
        # newest 100 releases misses older catalogue titles such as Breaking Bad.
        imdb_id = await _tmdb_tv_imdb_id(query)
        if not imdb_id:
            raise ProviderRequestError(
                "EZTV needs TMDB_API_KEY to resolve a show's IMDb ID; "
                "the latest-100 fallback is not a reliable catalogue search"
            )

        text = await _get(
            "https://eztvx.to/api/get-torrents",
            params={"imdb_id": imdb_id, "limit": "100", "page": "1"},
            headers={"Accept": "application/json", "Referer": "https://eztvx.to/"},
        )
        data = json.loads(text)
        out: list[TorrentResult] = []
        for item in data.get("torrents", []) or []:
            title = item.get("title") or ""
            out.append(TorrentResult(
                title=title,
                magnet=item.get("magnet_url", ""),
                provider="eztv",
                size_bytes=parse_int(item.get("size_bytes")),
                seeders=parse_int(item.get("seeds")),
                leechers=parse_int(item.get("peers")),
                category_hint="series",
                info_hash=(item.get("hash") or "").upper(),
            ))
        return out


class YtsSite(TorrentSite):
    id = "yts"
    label = "YTS"

    def categories(self):
        return ("movies",)

    async def search(self, query, category="all"):
        if category not in ("all", "movies"):
            return []
        # yts.mx DNS/availability is inconsistent on some hosted networks.
        # Try the primary endpoint first, then the currently documented API
        # mirror as a fallback. An empty result from the first host also gets
        # a fallback attempt rather than being treated as a definitive miss.
        payload = None
        errors = []
        endpoints = (
            "https://yts.mx/api/v2/list_movies.json",
            "https://movies-api.accel.li/api/v2/list_movies.json",
        )
        for endpoint in endpoints:
            try:
                text = await _get(
                    endpoint,
                    params={"query_term": query, "limit": "50"},
                    headers={"Accept": "application/json", "Referer": "https://yts.mx/"},
                )
                candidate = json.loads(text)
                candidate_data = candidate.get("data") or {}
                if candidate_data.get("movies"):
                    payload = candidate
                    break
                payload = candidate
            except Exception as exc:  # noqa: BLE001 - try next API host
                errors.append(str(exc))
        if payload is None:
            raise ProviderRequestError("; ".join(errors) or "YTS API unavailable")
        data = payload.get("data") or {}
        out: list[TorrentResult] = []
        for movie in data.get("movies", []) or []:
            for tor in movie.get("torrents", []) or []:
                info_hash = (tor.get("hash") or "").upper()
                title = f"{movie.get('title')} ({movie.get('year')}) {tor.get('quality')} {tor.get('type')}"
                out.append(TorrentResult(
                    title=title.strip(),
                    magnet=build_magnet(info_hash, title),
                    provider="yts",
                    size_bytes=parse_int(tor.get("size_bytes")),
                    seeders=parse_int(tor.get("seeds")),
                    leechers=parse_int(tor.get("peers")),
                    category_hint="movies",
                    quality_hint=str(tor.get("quality", "")).replace("p", ""),
                    info_hash=info_hash,
                    extra={"imdb": movie.get("imdb_code", ""), "rating": movie.get("rating")},
                ))
        return out


class TorrentGalaxySite(TorrentSite):
    id = "torrentgalaxy"
    label = "TorrentGalaxy"

    async def search(self, query, category="all"):
        text = await _get("https://torrentgalaxy.to/rss.xml", params={"search": query})
        if not text:
            return []
        return _generic_rss(text, "torrentgalaxy")


class AnimetoshoSite(TorrentSite):
    id = "animetosho"
    label = "AnimeTosho"

    def categories(self):
        return ("anime",)

    async def search(self, query, category="all"):
        if category not in ("all", "anime"):
            return []
        text = await _get("https://animetosho.org/feed/atom", params={"q": query})
        if not text:
            return []
        return _generic_rss(text, "animetosho")


def _generic_rss(text: str, provider: str) -> list[TorrentResult]:
    import feedparser

    feed = feedparser.parse(text)
    out: list[TorrentResult] = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        content = " ".join(
            str(part.get("value", "")) for part in (entry.get("content") or [])
            if isinstance(part, dict)
        )
        size_source = " ".join((str(summary), content))
        magnet = _extract_magnet(link, summary, content, entry.get("id", ""))
        enclosure = ""
        if entry.get("enclosures"):
            enclosure = entry["enclosures"][0].get("href", "")
        if not magnet:
            magnet = _extract_magnet(enclosure)
        if not magnet and not link:
            continue
        out.append(TorrentResult(
            title=title,
            magnet=magnet or link,
            provider=provider,
            size_bytes=parse_size(size_source),
            pub_date=entry.get("published", ""),
            page_url=link,
        ))
    return out


# ---------------------------------------------------------------------------
# Custom, file driven providers
# ---------------------------------------------------------------------------
class CustomRssSite(TorrentSite):
    def __init__(self, cfg: dict):
        self.id = cfg.get("id") or "custom"
        self.label = cfg.get("label") or self.id
        self._cfg = cfg

    async def search(self, query, category="all"):
        url = self._cfg.get("url", "")
        if "{query}" in url:
            url = url.replace("{query}", quote_plus(query))
            text = await _get(url)
        else:
            params = dict(self._cfg.get("params", {}))
            params.update({self._cfg.get("query_param", "q"): query})
            text = await _get(url, params=params)
        if not text:
            return []
        return _generic_rss(text, self.id)


class CustomJsonSite(TorrentSite):
    def __init__(self, cfg: dict):
        self.id = cfg.get("id") or "custom"
        self.label = cfg.get("label") or self.id
        self._cfg = cfg

    @staticmethod
    def _dig(data, dotted: str):
        for key in dotted.split("."):
            if key == "":
                continue
            if isinstance(data, list):
                data = data[int(key)]
            else:
                data = data.get(key, {})
        return data

    async def search(self, query, category="all"):
        cfg = self._cfg
        url = cfg.get("url", "")
        params = dict(cfg.get("params", {}))
        if "{query}" in url:
            url = url.replace("{query}", quote_plus(query))
            text = await _get(url, params=params or None)
        else:
            params.update({cfg.get("query_param", "q"): query})
            text = await _get(url, params=params)
        if not text:
            return []
        try:
            data = json.loads(text)
        except ValueError:
            return []

        items = self._dig(data, cfg.get("items_path", "")) if cfg.get("items_path") else data
        if not isinstance(items, list):
            return []

        title_key = cfg.get("title_key", "name")
        magnet_key = cfg.get("magnet_key", "magnet")
        hash_key = cfg.get("hash_key", "info_hash")
        size_key = cfg.get("size_key", "size")
        seeds_key = cfg.get("seeders_key", "seeders")

        out: list[TorrentResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get(title_key, "")).strip()
            magnet = item.get(magnet_key, "") or ""
            if not magnet and hash_key:
                magnet = build_magnet(str(item.get(hash_key, "")).upper(), title)
            if not title or not magnet:
                continue
            out.append(TorrentResult(
                title=title,
                magnet=magnet,
                provider=self.id,
                size_bytes=parse_size(str(item.get(size_key, ""))),
                seeders=parse_int(item.get(seeds_key)),
                category_hint=cfg.get("category_hint", ""),
            ))
        return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
BUILTIN_SITES: dict[str, type[TorrentSite]] = {
    "nyaa": NyaaSite,
    "subsplease": SubsPleaseSite,
    "apibay": ApibaySite,
    "eztv": EztvSite,
    "yts": YtsSite,
    "torrentgalaxy": TorrentGalaxySite,
    "animetosho": AnimetoshoSite,
}

_custom_cache: list[TorrentSite] = []


def load_custom_sites(force: bool = False) -> list[TorrentSite]:
    global _custom_cache
    if _custom_cache and not force:
        return _custom_cache

    sites: list[TorrentSite] = []
    path = Var.CUSTOM_SITES_FILE
    if path and ospath.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            for cfg in raw if isinstance(raw, list) else raw.get("sites", []):
                if not cfg.get("enabled", True):
                    continue
                stype = cfg.get("type", "rss")
                if stype == "json":
                    sites.append(CustomJsonSite(cfg))
                else:
                    sites.append(CustomRssSite(cfg))
        except Exception as exc:  # noqa: BLE001
            LOGS.error(f"[torrent_sites] Failed to load {path}: {exc}")
    _custom_cache = sites
    return sites


def get_sites(ids: Iterable[str] | None = None) -> list[TorrentSite]:
    ids = list(ids) if ids else list(Var.TORRENT_SITES)
    custom = {site.id: site for site in load_custom_sites()}
    sites: list[TorrentSite] = []
    for site_id in ids:
        if site_id in BUILTIN_SITES:
            sites.append(BUILTIN_SITES[site_id]())
        elif site_id in custom:
            sites.append(custom[site_id])
    return sites


def all_site_ids() -> list[str]:
    return list(BUILTIN_SITES) + [s.id for s in load_custom_sites()]
