# config.py
from os import getenv
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

load_dotenv()
LOGS = logging.getLogger(__name__)


def _normalize_ffcode(cmd: str | None) -> str | None:
    """Make user-supplied ffmpeg commands robust.

    ``-map 0:v`` also matches mjpeg cover art (a bogus extra video stream) and
    ``-map 0:s`` aborts the whole run when the source has no subtitles. Switch
    to the ``V`` (real video only) plus optional ``a?``/``s?`` form so encodes
    succeed on every release, including ones with no subtitle track.
    """
    if not cmd:
        return cmd
    cmd = cmd.replace("-map 0:v -map 0:a -map 0:s", "-map 0:V -map 0:a? -map 0:s?")
    cmd = cmd.replace("-map 0:v -map 0:a", "-map 0:V -map 0:a?")
    return cmd


class Var:
    API_ID = getenv("API_ID", "22225430")
    API_HASH = getenv("API_HASH", "4c5c28abd62233ef4b993fb972f83262")
    BOT_TOKEN = getenv("BOT_TOKEN", "8167289688:AAE-eeWDiRD1EcX9IWF_cN72aPefZwtKYZI")
    DB_URI = getenv("DB_URI", "")
    DB_NAME = getenv("DB_NAME", "Cluster0")
    BAN_SUPPORT = getenv("BAN_SUPPORT", "https://t.me/AnimeNovaChat")
    FSUB_LINK_EXPIRY = int(getenv("FSUB_LINK_EXPIRY", "120"))
    CHANNEL_ID = int(getenv("CHANNEL_ID", "0"))
    MHCHANNEL_URL = getenv("MHCHANNEL_URL", "https://t.me/+FiSlYftjwnAzMzVl")
    ANIME = getenv("ANIME", "Is It Wr2131ong to Try to Pi123ck Up Girls in a Dungeon?")
    CUSTOM_BANNER = getenv("CUSTOM_BANNER", "https://ibb.co/5xjBCXKp")

    PROTECT_CONTENT = True if getenv('PROTECT_CONTENT', "False") == "True" else False 
    BACKUP_CHANNEL = int(getenv("BACKUP_CHANNEL", "-1003844678491"))
    LOG_CHANNEL = int(getenv("LOG_CHANNEL", "-1002195760778"))
    MAIN_CHANNEL = int(getenv("MAIN_CHANNEL", "-1002486563630"))
    FILE_STORE = int(getenv("FILE_STORE", "-1002623405354"))
    ADMINS = list(map(int, getenv("ADMINS", "6039119180 7955996369").split()))

    RSS_ITEMS = getenv("RSS_ITEMS", "").split()
    SEND_SCHEDULE = getenv("SEND_SCHEDULE", "True").lower() == "true"
    BRAND_UNAME = getenv("BRAND_UNAME", "@Nova_Networks")

    FFCODE_1080p = _normalize_ffcode(getenv("FFCODE_1080"))
    FFCODE_720p = _normalize_ffcode(getenv("FFCODE_720"))
    FFCODE_480p = _normalize_ffcode(getenv("FFCODE_480"))
    FFCODE_360p = _normalize_ffcode(getenv("FFCODE_360"))
    FFCODE_HDRip = getenv("FFCODE_HDRip")
    QUALS = getenv("QUALS", "480 720 1080 HDRip").split()

    DISABLE_CHANNEL_BUTTON = getenv("DISABLE_CHANNEL_BUTTON", None) == 'True'
    AS_DOC = getenv("AS_DOC", "True").lower() == "true"
    # Telegram bots can upload at most 2000 MiB per file; files above
    # MAX_UPLOAD_SIZE (MiB) are split into playable parts before upload.
    MAX_UPLOAD_SIZE = int(getenv("MAX_UPLOAD_SIZE", "1900"))
    THUMB = getenv("THUMB")
    START_PIC = getenv("START_PIC","https://ibb.co/5xjBCXKp")
    FORCE_PIC = getenv("FORCE_PIC", "https://ibb.co/5xjBCXKp")
    # 16:9 image used on every channel post (the post header). Thumbnails on the
    # uploaded FILES are chosen separately in ⚙️ Settings -> Thumbnail.
    POST_PIC = getenv("POST_PIC", "https://i.ibb.co/7NLDxTWF/x.jpg")

    # ──────────────────────────────────────────────────────────────────
    #  FINDER / LEECHER BOT SETTINGS
    #  Search -> leech -> post pipeline settings.
    # ──────────────────────────────────────────────────────────────────
    # Channel where finished posts (with download buttons) are published.
    POST_CHANNEL = int(getenv("POST_CHANNEL", "0"))

    # "filename" = organise posts by parsed title, "imdb" = group by TMDB/IMDb id.
    POST_GROUPING = getenv("POST_GROUPING", "filename").lower()

    # Comma separated list of torrent providers to search.
    # Built-in ids: nyaa, subsplease, apibay, eztv, yts, torrentgalaxy, animetosho
    TORRENT_SITES = [s.strip() for s in getenv(
        "TORRENT_SITES",
        "nyaa,subsplease,apibay,eztv,yts"
    ).split(",") if s.strip()]

    # Extra user-defined providers (see custom_sites.json).
    CUSTOM_SITES_FILE = getenv("CUSTOM_SITES_FILE", "custom_sites.json")

    # Default filters used when the user has not picked any (comma separated).
    DEFAULT_CATEGORIES = [s.strip().lower() for s in getenv(
        "DEFAULT_CATEGORIES", "anime,series,movies"
    ).split(",") if s.strip()]
    DEFAULT_AUDIO = [s.strip().lower() for s in getenv(
        "DEFAULT_AUDIO", "sub,dub,dual,multi,hindi,english,tamil,telugu"
    ).split(",") if s.strip()]

    # Number of results shown per page and hard cap.
    RESULTS_PER_PAGE = int(getenv("RESULTS_PER_PAGE", "10"))
    MAX_RESULTS = int(getenv("MAX_RESULTS", "60"))

    # Feature defaults (can be toggled live from the bot's settings menu).
    # METADATA_MODE: "auto" (fetch from AniList/TMDB) | "custom" (use the
    # values saved in the bot's Metadata editor) | "off" (no metadata).
    METADATA_ON = getenv("METADATA_ON", "True").lower() == "true"
    METADATA_MODE = getenv("METADATA_MODE",
                           "auto" if METADATA_ON else "off").lower()
    THUMBNAIL_ON = getenv("THUMBNAIL_ON", "True").lower() == "true"
    ENCODING_ON = getenv("ENCODING_ON", "True").lower() == "true"
    DIRECT_MULTI_QUALITY = getenv("DIRECT_MULTI_QUALITY", "True").lower() == "true"
    AUTO_EXTRACT = getenv("AUTO_EXTRACT", "True").lower() == "true"
    AUTO_POST = getenv("AUTO_POST", "True").lower() == "true"

    # TMDB (used for movie / series metadata). Optional.
    TMDB_API_KEY = getenv("TMDB_API_KEY", "")

    # Editable caption template. Placeholders: {title} {season} {episode}
    # {audio} {subtitles} {quality} {languages} {year} {genres} {plot}
    # {rating} {status} {filename} {size} {brand}
    CAPTION_TEMPLATE = getenv("CAPTION_TEMPLATE", "")

    # Editable uploaded-file name template. Same placeholders as the caption.
    FILENAME_TEMPLATE = getenv("FILENAME_TEMPLATE", "")


# ✅ Required variable validation (outside the class)
REQUIRED_VARS = ["API_ID", "API_HASH", "BOT_TOKEN", "DB_URI"]
for var_name in REQUIRED_VARS:
    if not getattr(Var, var_name):
        LOGS.critical(f"Missing required environment variable: {var_name}")
        exit(1)
        #--------------------------------------------


LOG_FILE_NAME = "log.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
