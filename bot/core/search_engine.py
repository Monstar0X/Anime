"""Aggregate torrent search across providers, filter, rank and group results."""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass, field

import anitopy

from config import Var, LOGS
from .torrent_sites import TorrentResult, get_sites

# ── detection helpers ───────────────────────────────────────────────────────
_SXXEXX = re.compile(r"\bS(\d{1,2})[\s._-]?E(\d{1,3})\b", re.IGNORECASE)
_SEASON = re.compile(r"\bSeason[\s._-]?(\d{1,2})\b", re.IGNORECASE)
_BARE_EP = re.compile(r"(?:^|[\s\-_\[(])(?:EP?|Episode)[\s._-]?(\d{1,3})\b", re.IGNORECASE)
_DASH_EP = re.compile(r"\s-\s(\d{1,3})(?:\s|$|\[|\()")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")

_P_QUALITY = re.compile(r"\b(2160|1080|720|480|360)\s?p\b", re.IGNORECASE)
_BARE_QUALITY = re.compile(r"\b(1080|720|480|360)\b")

_AUDIO_TAGS = {
    "dual": ("dual audio", "dual-audio", "dual.audio", "dual"),
    "multi": ("multi audio", "multi-audio", "multi.audio", "multi"),
    "hindi": ("hindi", "hin"),
    "tamil": ("tamil", "tam"),
    "telugu": ("telugu", "tel"),
    "english": ("english dub", "eng dub", "eng-dub", "dubbed", "dub"),
    "sub": ("subbed", "hardsub", "softsub", "eng sub", "english sub", "subs", "sub"),
}

_ANIME_HINTS = ("subsplease", "animetosho", "horriblesubs", "erai-raws", "judas")
_ANIME_KEYWORDS = ("anime", "ova", "ona", "opening", "ending", "raw")


def detect_quality(title: str) -> str:
    low = title.lower()
    if "hdrip" in low or "hd-rip" in low or "hd.rip" in low or "hd_rip" in low:
        return "2160"
    m = _P_QUALITY.search(title)
    if m:
        return m.group(1)
    if "4k" in low or "uhd" in low:
        return "2160"
    m = _BARE_QUALITY.search(title)
    if m:
        return m.group(1)
    return ""


def quality_label(quality: str) -> str:
    """Map a detected quality to the bot's display label (2160 -> HDRip)."""
    if quality in ("2160", "hdrip", "4k"):
        return "HDRip"
    return quality or ""


def detect_audio(title: str, provider: str = "") -> set[str]:
    low = title.lower()
    tags: set[str] = set()
    for tag, needles in _AUDIO_TAGS.items():
        if any(n in low for n in needles):
            tags.add(tag)
    # SubsPlease releases are Japanese-audio releases with English subtitles
    # unless the title explicitly advertises a different dub/audio track.
    if provider == "subsplease" and not tags:
        tags.add("japanese")
    # "dub" also implies English audio; keep both for caption richness.
    if "dub" in tags:
        tags.add("english")
    return tags or {"unknown"}


def detect_subtitles(title: str, provider: str = "") -> list[str]:
    low = title.lower()
    if "multi sub" in low or "multi-sub" in low or "multisub" in low:
        return ["Multi"]
    if "sub" in low or provider == "subsplease":
        return ["English"]
    return []


def detect_languages(title: str) -> list[str]:
    tags = detect_audio(title)
    pretty = {
        "japanese": "Japanese",
        "dual": "Dual Audio",
        "multi": "Multi Audio",
        "hindi": "Hindi",
        "tamil": "Tamil",
        "telugu": "Telugu",
        "english": "English",
        "sub": "Japanese",
    }
    return [pretty[t] for t in ("hindi", "tamil", "telugu", "english", "japanese", "dual", "multi", "sub")
            if t in tags]


def _parse_season_episode(title: str) -> tuple[str, str]:
    season = episode = ""
    m = _SXXEXX.search(title)
    if m:
        season, episode = m.group(1), m.group(2)
        return season, episode
    m = _SEASON.search(title)
    if m:
        season = m.group(1)
    m = _BARE_EP.search(title) or _DASH_EP.search(title)
    if m:
        episode = m.group(1)
    return season, episode


def detect_categories(result: TorrentResult) -> list[str]:
    title = result.title
    low = title.lower()
    hint = (result.category_hint or "").lower()
    provider = result.provider

    cats: list[str] = []
    season, episode = _parse_season_episode(title)

    anime = provider in _ANIME_HINTS or "anime" in hint or any(k in low for k in _ANIME_KEYWORDS)
    movies = provider == "yts" or "movie" in hint or "movies" in hint
    series = provider == "eztv" or "tv" in hint or "series" in hint

    if not (anime or movies or series):
        if _SXXEXX.search(title) or _SEASON.search(title):
            series = True
        elif episode and not season:
            anime = True
        elif _YEAR.search(title) and not episode:
            movies = True

    if anime:
        cats.append("anime")
    if series:
        cats.append("series")
    if movies:
        cats.append("movies")
    return cats or ["anime", "series", "movies"]


# ── cleaning / grouping ─────────────────────────────────────────────────────
_CLEAN_NOISE = re.compile(
    r"\b(1080p?|720p?|480p?|360p?|2160p?|4k|uhd|hdrip|webrip|web-dl|webdl|web|"
    r"bluray|blu-ray|bdrip|brrip|hdtv|dvdrip|x264|x265|h264|h265|hevc|avc|10bit|8bit|"
    r"aac|ac3|eac3|ddp?5\.1|dd5\.1|atmos|dual audio|multi audio|multi|dual|"
    r"hindi|tamil|telugu|eng|english|jap|japanese|dub|subbed|subs|sub|"
    r"complete|batch|season|remux|proper|repack|hdr|dv|sdr)\b",
    re.IGNORECASE,
)


def clean_title(title: str) -> str:
    text = re.sub(r"\[[^\]]*\]", " ", title)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = _CLEAN_NOISE.sub(" ", text)
    text = _SXXEXX.sub(" ", text)
    text = re.sub(r"[._\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def release_key(result: TorrentResult) -> str:
    season, episode = _parse_season_episode(result.title)
    parsed = anitopy.parse(result.title) or {}
    core = parsed.get("anime_title") or clean_title(result.title)
    return f"{core.strip().lower()}|s{season}|e{episode}"


# ── relevance ───────────────────────────────────────────────────────────────
def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 1]


def relevance(query: str, title: str) -> float:
    q_tokens = _tokens(query)
    if not q_tokens:
        return 0.0
    t_tokens = set(_tokens(title))
    matched = sum(1 for tok in q_tokens if any(tok in cand for cand in t_tokens))
    return matched / len(q_tokens)


def score_result(query: str, result: TorrentResult) -> float:
    rel = relevance(query, result.title)
    seeders = max(result.seeders, 0)
    seed_score = min(math.log10(seeders + 1) * 6, 24)
    quality = detect_quality(result.title)
    score = rel * 100 + seed_score
    if quality:
        score += 6
    if result.magnet and not result.magnet.startswith("magnet:"):
        score -= 25  # not directly leechable
    if rel < 0.5:
        score -= 40
    return round(score, 2)


# ── filtering ───────────────────────────────────────────────────────────────
def matches_filters(result: TorrentResult, categories: set[str], audio: set[str],
                    qualities: set[str]) -> bool:
    if categories:
        if not (set(detect_categories(result)) & categories):
            return False

    if qualities:
        q = quality_label(detect_quality(result.title))
        if q not in qualities:
            return False

    if audio:
        # Title-based audio match. When a specific track is requested we only
        # keep releases that actually advertise it (dual/multi count as their
        # own selectable options, not as every language).
        tags = detect_audio(result.title, result.provider) - {"unknown"}
        if not (tags & audio):
            return False
    return True


# ── aggregation ─────────────────────────────────────────────────────────────
@dataclass
class SearchOutcome:
    results: list[TorrentResult] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)
    providers_failed: list[str] = field(default_factory=list)
    provider_counts: dict[str, int] = field(default_factory=dict)
    provider_errors: dict[str, str] = field(default_factory=dict)


async def search_all(query: str, category: str = "all", sites: list[str] | None = None,
                     per_site_timeout: int = 20) -> SearchOutcome:
    providers = get_sites(sites)
    outcome = SearchOutcome()

    semaphore = asyncio.Semaphore(4)

    async def run(site):
        async with semaphore:
            try:
                items = await asyncio.wait_for(
                    site.search(query, category), timeout=per_site_timeout
                )
                return site, items, ""
            except asyncio.TimeoutError:
                reason = "timeout"
            except Exception as exc:  # noqa: BLE001 - isolate provider failures
                reason = str(exc) or exc.__class__.__name__
            LOGS.warning(f"[search] {site.id} failed: {reason}")
            return site, None, reason

    for site, items, error in await asyncio.gather(*(run(s) for s in providers)):
        if items is None:
            outcome.providers_failed.append(site.id)
            outcome.provider_errors[site.id] = error
            continue
        outcome.providers_used.append(site.id)
        outcome.provider_counts[site.id] = len(items)
        outcome.results.extend(items)

    seen: set[str] = set()
    unique: list[TorrentResult] = []
    for res in outcome.results:
        key = res.info_hash.lower() or res.magnet.lower() or res.title.lower()
        if key in seen:
            continue
        seen.add(key)
        res.score = score_result(query, res)
        unique.append(res)

    unique.sort(key=lambda r: (r.score, r.seeders), reverse=True)
    outcome.results = unique[: Var.MAX_RESULTS]
    return outcome


def group_multi_quality(results: list[TorrentResult]) -> dict[str, list[TorrentResult]]:
    """Group results that belong to the same release but differ in quality."""
    groups: dict[str, list[TorrentResult]] = {}
    for res in results:
        groups.setdefault(release_key(res), []).append(res)
    return groups


def group_qualities(results: list[TorrentResult]) -> dict[str, TorrentResult]:
    """Return one best result per quality label for a multi-quality release."""
    best: dict[str, TorrentResult] = {}
    for res in results:
        label = quality_label(detect_quality(res.title))
        if not label:
            continue
        current = best.get(label)
        if current is None or res.seeders > current.seeders:
            best[label] = res
    return best
