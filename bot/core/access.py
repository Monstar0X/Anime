"""Access control: the bot only *acts* for its owner / admins.

Everyone can open the menus and look around, but searching, leeching and
changing settings are restricted to :data:`config.Var.ADMINS`.
"""

from __future__ import annotations

from config import Var

DENY = "🚫 ᴏɴʟʏ ᴛʜᴇ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ ᴛʜɪs."


def is_admin(user_id: int | None) -> bool:
    try:
        return int(user_id) in {int(a) for a in Var.ADMINS}
    except (TypeError, ValueError):
        return False


async def deny(query) -> None:
    """Reject a callback query with a popup."""
    await query.answer(DENY, show_alert=True)
