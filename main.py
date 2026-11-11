import pyrogram.utils

from bot.__main__ import main
from bot.core.bot_instance import bot_loop

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

if __name__ == "__main__":
    bot_loop.run_until_complete(main())
