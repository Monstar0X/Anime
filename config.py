# config.py
from os import getenv
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

load_dotenv()
LOGS = logging.getLogger(__name__)

class Var:
    API_ID = getenv("API_ID", "22225430")
    API_HASH = getenv("API_HASH", "4c5c28abd62233ef4b993fb972f83262")
    BOT_TOKEN = getenv("BOT_TOKEN", "8167289688:AAE-eeWDiRD1EcX9IWF_cN72aPefZwtKYZI")
    DB_URI = getenv("DB_URI", "mongodb+srv://Jas:jasmehra13221422@cluster0.xbyevs3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DB_NAME = getenv("DB_NAME", "Auto Anime")
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
    FILE_STORE = int(getenv("FILE_STORE", "-1002310535906"))
    ADMINS = list(map(int, getenv("ADMINS", "6039119180").split()))

    RSS_ITEMS = getenv("RSS_ITEMS", "").split()
    SEND_SCHEDULE = getenv("SEND_SCHEDULE", "True").lower() == "true"
    BRAND_UNAME = getenv("BRAND_UNAME", "@Nova_Networks")

    FFCODE_1080 = getenv("FFCODE_1080")
    FFCODE_720 = getenv("FFCODE_720")
    FFCODE_480 = getenv("FFCODE_480")
    FFCODE_360 = getenv("FFCODE_360")
    FFCODE_HDRip = getenv("FFCODE_HDRip")
    QUALS = getenv("QUALS", "480 720 1080 HDRip").split()

    DISABLE_CHANNEL_BUTTON = getenv("DISABLE_CHANNEL_BUTTON", None) == 'True'
    AS_DOC = getenv("AS_DOC", "True").lower() == "true"
    THUMB = getenv("THUMB")
    START_PIC = getenv("START_PIC","https://ibb.co/5xjBCXKp")
    FORCE_PIC = getenv("FORCE_PIC", "https://ibb.co/5xjBCXKp")


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
