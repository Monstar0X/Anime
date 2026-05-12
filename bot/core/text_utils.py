from calendar import month_name
from datetime import datetime
from random import choice
from asyncio import sleep as asleep
from aiohttp import ClientSession
import xml.etree.ElementTree as ET
from anitopy import parse

from bot.core.bot_instance import bot, ani_cache
from config import Var, LOGS
from .ffencoder import ffargs
from .func_utils import handle_logs
from .reporter import rep


CAPTION_FORMAT = """<blockquote><b>{title}</b></blockquote>

──────────────────────
➥ <b>Season:</b> {season_number}
➤ <b>Episode:</b> {ep_no}
➥ <b>Audio:</b> {lang_info}
➥ <b>Status:</b> {status}
➥ <b>Score:</b> {avg_score}
➥ <b>Genres:</b> {genres}
──────────────────────

<blockquote>{plot}</blockquote>

<blockquote>
● ᴜsᴇ <b><a href="https://play.google.com/store/apps/details?id=org.videolan.vlc">ᴠʟᴄ</a></b>
ᴏʀ ᴀɴʏ ᴏᴛʜᴇʀ
<b><a href="https://play.google.com/store/apps/details?id=com.mxtech.videoplayer.ad">ɢᴏᴏᴅ ᴠɪᴅᴇᴏ</a></b>
ᴘʟᴀʏᴇʀ ᴀᴘᴘ ᴛᴏ ᴡᴀᴛᴄʜ ᴛʜᴇ ᴇᴘɪsᴏᴅᴇs ᴡɪᴛʜ
ɢᴏᴏᴅ ᴇxᴘᴇʀɪᴇɴᴄᴇ!
</blockquote>
"""


GENRES_EMOJI = {
    "Action": "🔥",
    "Adventure": "🗺️",
    "Comedy": "😂",
    "Drama": "🎭",
    "Ecchi": "😏",
    "Fantasy": "✨",
    "Horror": "👻",
    "Mahou Shoujo": "🪄",
    "Mecha": "🤖",
    "Music": "🎵",
    "Mystery": "🕵️",
    "Psychological": "🧠",
    "Romance": "❤️",
    "Sci-Fi": "🚀",
    "Slice of Life": "🌸",
    "Sports": "🏆",
    "Supernatural": "🔮",
    "Thriller": "⚠️",
    "Military": "🎖️",
    "Historical": "📜",
    "Martial Arts": "🥋",
    "Game": "🎮",
    "Time Travel": "⏳",
    "Detective": "🕵️",
    "Cyberpunk": "🌃",
    "Post-Apocalyptic": "☣️",
    "Music & Idol": "🎤"
}


GENRE_NORMALIZATION = {
    "Action & Adventure": "Action",
    "Romantic Comedy": "Comedy",
    "Shounen": "Action",
    "Shoujo": "Romance",
    "Seinen": "Drama",
    "Josei": "Drama",
    "Slice-of-Life": "Slice of Life",
    "Magical Girl": "Mahou Shoujo",
    "Science Fiction": "Sci-Fi",
    "Psychological Thriller": "Psychological",
    "Suspense": "Thriller",
    "Martial-Arts": "Martial Arts",
    "Fantasy Adventure": "Fantasy",
    "Post Apocalypse": "Post-Apocalyptic",
    "Cyber Punk": "Cyberpunk",
    "Historical Drama": "Historical",
    "Romance Comedy": "Romance",
    "Action Comedy": "Action",
    "Super Power": "Supernatural",
    "Game Based": "Game",
    "Music Idol": "Music & Idol",
    "Sports Drama": "Sports",
    "Military Sci-Fi": "Military",
    "Time-Travel": "Time Travel",
    "Detective Mystery": "Detective"
}


ANIME_GRAPHQL_QUERY = """
query ($id: Int, $search: String, $seasonYear: Int) {
  Media(
    id: $id,
    type: ANIME,
    format_not_in: [MOVIE, MUSIC, MANGA, NOVEL, ONE_SHOT],
    search: $search,
    seasonYear: $seasonYear
  ) {
    id
    idMal
    title {
      romaji
      english
      native
    }
    status(version: 2)
    description(asHtml: false)
    startDate {
      year
      month
      day
    }
    endDate {
      year
      month
      day
    }
    episodes
    genres
    averageScore
    coverImage {
      large
    }
  }
}
"""


def normalize_genres(genres: list) -> list:
    normalized = []

    for genre in genres or []:
        genre_key = GENRE_NORMALIZATION.get(genre, genre)

        if genre_key in GENRES_EMOJI:
            normalized.append(genre_key)

    return normalized


class AniLister:
    def __init__(self, anime_name: str, year: int) -> None:
        self.__api = "https://graphql.anilist.co"
        self.__ani_name = anime_name
        self.__ani_year = year
        self.__vars = {
            'search': self.__ani_name,
            'seasonYear': self.__ani_year
        }

    def __update_vars(self, year: bool = True) -> None:
        if year:
            self.__ani_year -= 1
            self.__vars['seasonYear'] = self.__ani_year
        else:
            self.__vars = {'search': self.__ani_name}

    async def post_data(self):
        async with ClientSession() as sess:
            async with sess.post(
                self.__api,
                json={
                    'query': ANIME_GRAPHQL_QUERY,
                    'variables': self.__vars
                }
            ) as resp:
                return (
                    resp.status,
                    await resp.json(),
                    resp.headers
                )

    async def get_anidata(self):
        cache_key = f"{self.__ani_name}:{self.__ani_year}"

        if cache_key in ani_cache:
            return ani_cache[cache_key]

        res_code, resp_json, res_heads = await self.post_data()

        while res_code == 404 and self.__ani_year > 2020:
            self.__update_vars()

            await rep.report(
                f"AniList Query Name: {self.__ani_name}, Retrying with {self.__ani_year}",
                "warning",
                log=False
            )

            res_code, resp_json, res_heads = await self.post_data()

        if res_code == 404:
            self.__update_vars(year=False)
            res_code, resp_json, res_heads = await self.post_data()

        if res_code == 200:
            data = resp_json.get('data', {}).get('Media', {}) or {}
            data["genres"] = normalize_genres(data.get("genres", []))

            ani_cache[cache_key] = data
            return data

        elif res_code == 429:
            retry_after = int(res_heads.get('Retry-After', 10))
            await asleep(retry_after * 1.5)
            return await self.get_anidata()

        elif res_code in [500, 501, 502]:
            await asleep(5)
            return await self.get_anidata()

        await rep.report(
            f"AniList API Error: {res_code}",
            "error",
            log=False
        )

        return {}


class TextEditor:
    def __init__(self, name):
        self.__name = name
        self.adata = {}
        self.pdata = parse(name)
        self.anilister = AniLister(self.__name, datetime.now().year)

    async def load_anilist(self):
        cache_names = set()

        variations = [
            (False, False),
            (False, True),
            (True, False),
            (True, True),
            "clean"
        ]

        for var in variations:

            if var == "clean":
                ani_name = self.pdata.get("anime_title")

            else:
                no_s, no_y = var
                ani_name = await self.parse_name(no_s, no_y)

            if not ani_name or ani_name in cache_names:
                continue

            cache_names.add(ani_name)

            self.anilister._AniLister__ani_name = ani_name
            self.anilister._AniLister__vars['search'] = ani_name

            self.adata = await self.anilister.get_anidata()

            if self.adata:
                break

    @handle_logs
    async def parse_name(self, no_s=False, no_y=False):
        anime_name = self.pdata.get("anime_title") or self.__name
        anime_season = self.pdata.get("anime_season")
        anime_year = self.pdata.get("anime_year")

        if anime_name:
            pname = anime_name

            if not no_s and self.pdata.get("episode_number") and anime_season:
                pname += f" {anime_season}"

            if not no_y and anime_year:
                pname += f" {anime_year}"

            return pname

        return anime_name

    @handle_logs
    async def get_poster(self):
        anime_id = self.adata.get("id")

        if anime_id and str(anime_id).isdigit():
            return f"https://img.anili.st/media/{anime_id}"

        return "https://envs.sh/YsH.jpg"

    @handle_logs
    async def get_upname(self, qual=""):
        anime_name = self.pdata.get("anime_title")

        codec = (
            'HEVC'
            if 'libx265' in ffargs[qual]
            else 'AV1'
            if 'libaom-av1' in ffargs[qual]
            else ''
        )

        lang = 'SUB' if 'sub' in self.__name.lower() else 'Sub'

        anime_season = (
            str(ani_s[-1])
            if (ani_s := self.pdata.get('anime_season', '01'))
            and isinstance(ani_s, list)
            else str(ani_s)
        )

        titles = self.adata.get('title', {})

        return (
            f"[S{anime_season}-E{self.pdata.get('episode_number')}] "
            f"{titles.get('english') or titles.get('romaji') or titles.get('native')} "
            f"{'['+qual+'p]' if qual else ''} "
            f"{'['+codec.upper()+'] ' if codec else ''}"
            f"[{lang}] {Var.BRAND_UNAME}.mkv"
        )

    @handle_logs
    async def get_caption(self):

        sd = self.adata.get('startDate', {})

        try:
            month_idx = int(sd.get('month')) if sd.get('month') else None

            startdate = (
                f"{month_name[month_idx]} {sd['day']}, {sd['year']}"
                if sd.get('day') and sd.get('year') and month_idx
                else "N/A"
            )

        except:
            startdate = "N/A"

        ed = self.adata.get('endDate', {})

        try:
            month_idx = int(ed.get('month')) if ed.get('month') else None

            enddate = (
                f"{month_name[month_idx]} {ed['day']}, {ed['year']}"
                if ed.get('day') and ed.get('year') and month_idx
                else "N/A"
            )

        except:
            enddate = "N/A"

        titles = self.adata.get("title", {})

        audio_lang = "Japanese"

        lower_name = self.__name.lower()

        if "dual" in lower_name or "multi" in lower_name:
            audio_lang = "Dual Audio"

        elif "dub" in lower_name:
            audio_lang = "English"

        anime_season = (
            str(ani_s[-1])
            if (ani_s := self.pdata.get('anime_season', '01'))
            and isinstance(ani_s, list)
            else str(ani_s)
        )

        desc = self.adata.get("description") or "N/A"

        if len(desc) > 200:
            desc = desc[:200] + "..."

        genres = ", ".join(
            f"{GENRES_EMOJI.get(x, '🎬')} #{x.replace(' ', '_').replace('-', '_')}"
            for x in (self.adata.get('genres') or [])
        )

        return CAPTION_FORMAT.format(
            title=titles.get('english')
                  or titles.get('romaji')
                  or titles.get('native')
                  or "N/A",

            season_number=anime_season,

            ep_no=self.pdata.get("episode_number") or "N/A",

            lang_info=audio_lang,

            genres=genres or "N/A",

            avg_score=(
                f"{self.adata.get('averageScore')}%"
                if self.adata.get('averageScore')
                else "N/A"
            ),

            status=self.adata.get("status") or "N/A",

            start_date=startdate,

            end_date=enddate,

            plot=desc,

            cred=Var.BRAND_UNAME
        )