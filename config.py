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
    # Credentials are read from the environment only (see .env.example).
    API_ID = getenv("API_ID", "")
    API_HASH = getenv("API_HASH", "")
    BOT_TOKEN = getenv("BOT_TOKEN", "")
    DB_URI = getenv("DB_URI", "")
    DB_NAME = getenv("DB_NAME", "Cluster0")

    # Channels / admins
    LOG_CHANNEL = int(getenv("LOG_CHANNEL", "0"))
    CHANNEL_ID = int(getenv("CHANNEL_ID", "0"))
    FILE_STORE = int(getenv("FILE_STORE", "0"))
    ADMINS = list(map(int, getenv("ADMINS", "").split()))

    # Branding / force-subscribe
    BRAND_UNAME = getenv("BRAND_UNAME", "@Nova_Networks")
    BAN_SUPPORT = getenv("BAN_SUPPORT", "https://t.me/AnimeNovaChat")
    MHCHANNEL_URL = getenv("MHCHANNEL_URL", "https://t.me/+FiSlYftjwnAzMzVl")
    FSUB_LINK_EXPIRY = int(getenv("FSUB_LINK_EXPIRY", "120"))

    PROTECT_CONTENT = getenv("PROTECT_CONTENT", "False").lower() == "true"
    DISABLE_CHANNEL_BUTTON = getenv("DISABLE_CHANNEL_BUTTON", "False").lower() == "true"

    # Encode profiles (one ffmpeg command per quality; {} placeholders are
    # input, progress file and output, in that order).
    FFCODE_1080 = _normalize_ffcode(getenv("FFCODE_1080"))
    FFCODE_720 = _normalize_ffcode(getenv("FFCODE_720"))
    FFCODE_480 = _normalize_ffcode(getenv("FFCODE_480"))
    FFCODE_360 = _normalize_ffcode(getenv("FFCODE_360"))
    FFCODE_HDRip = getenv("FFCODE_HDRip")
    QUALS = getenv("QUALS", "480 720 1080 HDRip").split()

    # Telegram bots can upload at most 2000 MiB per file; files above
    # MAX_UPLOAD_SIZE (MiB) are split into playable parts before upload.
    MAX_UPLOAD_SIZE = int(getenv("MAX_UPLOAD_SIZE", "1900"))
    AS_DOC = getenv("AS_DOC", "True").lower() == "true"

    # Artwork
    THUMB = getenv("THUMB")
    START_PIC = getenv("START_PIC", "https://ibb.co/5xjBCXKp")
    FORCE_PIC = getenv("FORCE_PIC", "https://ibb.co/5xjBCXKp")
    # 16:9 image used on every channel post (the post header). Thumbnails on the
    # uploaded FILES are chosen separately in Settings -> Thumbnail.
    POST_PIC = getenv("POST_PIC", "https://i.ibb.co/7NLDxTWF/x.jpg")

    # ──────────────────────────────────────────────────────────────────
    #  FINDER / LEECHER BOT SETTINGS
    #  Search -> leech -> post pipeline settings.
    # ──────────────────────────────────────────────────────────────────
    # Channel where finished posts (with download buttons) are published.
    POST_CHANNEL = int(getenv("POST_CHANNEL", "0"))

    # Comma separated list of torrent providers to search.
    # Built-in ids: nyaa, subsplease, apibay, eztv, yts, torrentgalaxy, animetosho
    TORRENT_SITES = [s.strip() for s in getenv(
        "TORRENT_SITES",
        "nyaa,subsplease,apibay,eztv,yts,torrentgalaxy"
    ).split(",") if s.strip()]

    # Extra user-defined providers (see custom_sites.json).
    CUSTOM_SITES_FILE = getenv("CUSTOM_SITES_FILE", "custom_sites.json")

    # Number of results shown per page and hard cap.
    RESULTS_PER_PAGE = int(getenv("RESULTS_PER_PAGE", "10"))
    MAX_RESULTS = int(getenv("MAX_RESULTS", "60"))

    # METADATA_MODE: "auto" (fetch from AniList/TMDB) | "custom" (use the
    # values saved in the bot's Metadata editor) | "off" (no metadata).
    METADATA_MODE = getenv("METADATA_MODE", "auto").lower()

    # Feature defaults (also toggled live from the bot's settings menu).
    AUTO_POST = getenv("AUTO_POST", "True").lower() == "true"

    # TMDB (used for movie / series metadata). Optional.
    TMDB_API_KEY = getenv("TMDB_API_KEY", "")

    # Editable caption template. Placeholders: {title} {season} {episode}
    # {audio} {subtitles} {quality} {languages} {year} {genres} {plot}
    # {rating} {status} {filename} {size} {brand}
    CAPTION_TEMPLATE = getenv("CAPTION_TEMPLATE", "")

    # Editable uploaded-file name template. Same placeholders as the caption.
    FILENAME_TEMPLATE = getenv("FILENAME_TEMPLATE", "")


# Required variable validation (outside the class)
REQUIRED_VARS = ["API_ID", "API_HASH", "BOT_TOKEN", "DB_URI"]
for var_name in REQUIRED_VARS:
    if not getattr(Var, var_name):
        LOGS.critical(f"Missing required environment variable: {var_name}")
        exit(1)

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
