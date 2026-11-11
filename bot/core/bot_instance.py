import os
import logging  # Added to resolve NameError
from asyncio import Queue, Semaphore
from logging import INFO, ERROR, FileHandler, StreamHandler, basicConfig, getLogger
from traceback import format_exc
from os import path as ospath, mkdir, system

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode
from uvloop import install
from datetime import datetime
from config import Var, LOGS

install()

basicConfig(
    format="[%(asctime)s] [%(name)s | %(levelname)s] - %(message)s [%(filename)s:%(lineno)d]",
    datefmt="%m/%d/%Y, %H:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO
)

getLogger("pyrogram").setLevel(ERROR)
LOGS = getLogger(__name__)

# Initialize shared objects
ffpids_cache = []
ffLock = Semaphore(3)
ffQueue = Queue()
ff_queued = dict()

# The encode commands call bare `ffmpeg`. If the system binary is absent, fall
# back to the static-ffmpeg wheel (a project dependency) and put it on PATH.
try:
    from shutil import which as _which
    if _which("ffmpeg") is None:
        import static_ffmpeg
        static_ffmpeg.add_paths()
except Exception as _ff_err:  # noqa: BLE001
    LOGS.warning(f"static-ffmpeg not available: {_ff_err}")

try:
    bot = Client(
        name="FinderBot",
        api_id=Var.API_ID,
        api_hash=Var.API_HASH,
        bot_token=Var.BOT_TOKEN,
        plugins=dict(root="bot/plugins"),
        parse_mode=ParseMode.HTML,
       
    )
    bot_loop = bot.loop
    sch = AsyncIOScheduler(timezone="Asia/Kolkata", event_loop=bot_loop)

except Exception as ee:
    LOGS.error(str(ee))
    exit(1)

# Ensure necessary directories
if Var.THUMB and not ospath.exists("thumb.jpg"):
    system(f"wget -q {Var.THUMB} -O thumb.jpg")
    LOGS.info("Thumbnail saved!")

os.makedirs("encode", exist_ok=True)
os.makedirs("thumbs", exist_ok=True)
os.makedirs("downloads", exist_ok=True)
