"""Generic admin utilities (uptime / ping / db latency)."""

import time
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Var
from bot.core.bot_instance import bot
from bot.core.database import db
from bot.core.func_utils import new_task


def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    hmm = len(time_list)
    for x in range(hmm):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time


async def get_db_response_time() -> float:
    start = time.time()
    await db.command("ping")
    end = time.time()
    return round((end - start) * 1000, 2)


async def get_ping(client: Client) -> float:
    start = time.time()
    await client.get_me()
    end = time.time()
    return round((end - start) * 1000, 2)


@bot.on_message(filters.command('ping') & filters.user(Var.ADMINS))
@new_task
async def stats(client: Client, message: Message):
    try:
        now = datetime.now()
        if not hasattr(bot, 'uptime'):
            uptime = "Uptime not available"
        else:
            delta = now - bot.uptime
            uptime = get_readable_time(delta.seconds)

        ping = await get_ping(bot)
        db_response_time = await get_db_response_time()

        stats_text = (
            f"Bot Uptime: {uptime}\n"
            f"Ping: {ping} ms\n"
            f"Database Response Time: {db_response_time} ms\n"
        )
        await message.reply_text(stats_text)
    except Exception as e:
        await message.reply_text(f"Error in ping command: {str(e)}")
