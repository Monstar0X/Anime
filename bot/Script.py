import os

class botmaker(object):
    START_MSG = """<b>ʜᴇʏ {first} 👋\n\n<blockquote>ɪ ᴀᴍ ᴀ sᴇᴀʀᴄʜ + ʟᴇᴇᴄʜ ʙᴏᴛ. ᴛᴀᴘ <b>🔍 ғɪɴᴅ ʜᴇʀᴇ</b>, ᴛʏᴘᴇ ᴀ ɴᴀᴍᴇ (ᴀɴɪᴍᴇ / sᴇʀɪᴇs / ᴍᴏᴠɪᴇ) ᴀɴᴅ ɪ ᴡɪʟʟ ᴘᴏsᴛ ᴛʜᴇ ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋs ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ.</blockquote></b>"""

    FORCE_MSG = """ʜᴇʟʟᴏ {first}\n\n<b>ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟs ᴀɴᴅ ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴏɴ ʀᴇʟᴏᴀᴅ button ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛᴇᴅ ꜰɪʟᴇ.</b>"""

    HELP_TXT = """<b><blockquote>sᴇᴀʀᴄʜ + ʟᴇᴇᴄʜ ʙᴏᴛ

❏ ᴜsᴇʀ ᴄᴏᴍᴍᴀɴᴅs
├ /start : ᴏᴘᴇɴ ᴛʜᴇ sᴇᴀʀᴄʜ ᴍᴇɴᴜ
├ /settings : ᴛᴏɢɢʟᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ / ᴛʜᴜᴍʙɴᴀɪʟ / ᴇɴᴄᴏᴅɪɴɢ ᴇᴛᴄ.
├ /about : ᴀʙᴏᴜᴛ ᴛʜᴇ ʙᴏᴛ
└ /help : ᴛʜɪs ᴍᴇssᴀɢᴇ

ᴛᴀᴘ <b>🔍 ғɪɴᴅ ʜᴇʀᴇ</b>, ᴛʏᴘᴇ ᴀ ɴᴀᴍᴇ, ᴘɪᴄᴋ ᴀ ʀᴇsᴜʟᴛ ʙʏ ɴᴜᴍʙᴇʀ ᴀɴᴅ ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴘᴏsᴛ ᴛʜᴇ ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋs.</blockquote></b>"""

    ABOUT_TXT = """<b><blockquote>
◈ sᴇᴀʀᴄʜ + ʟᴇᴇᴄʜ ʙᴏᴛ
◈ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴍᴜʟᴛɪ-ꜱɪᴛᴇ ᴛᴏʀʀᴇɴᴛ sᴇᴀʀᴄʜ
</blockquote></b>"""

    CMD_TXT = """<blockquote><b>» ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs:</b></blockquote>

<b>›› /dlt_time :</b> sᴇᴛ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇ  
<b>›› /check_dlt_time :</b> ᴄʜᴇᴄᴋ ᴄᴜʀʀᴇɴᴛ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇ  
<b>›› /dbroadcast :</b> ʙʀᴏᴀᴅᴄᴀsᴛ ᴅᴏᴄᴜᴍᴇɴᴛ / ᴠɪᴅᴇᴏ  
<b>›› /ban :</b> ʙᴀɴ ᴀ ᴜꜱᴇʀ  
<b>›› /unban :</b> ᴜɴʙᴀɴ ᴀ ᴜꜱᴇʀ  
<b>›› /banlist :</b> ɢᴇᴛ ʟɪsᴛ ᴏꜰ ʙᴀɴɴᴇᴅ ᴜꜱᴇʀs  
<b>›› /addchnl :</b> ᴀᴅᴅ ꜰᴏʀᴄᴇ sᴜʙ ᴄʜᴀɴɴᴇʟ  
<b>›› /delchnl :</b> ʀᴇᴍᴏᴠᴇ ꜰᴏʀᴄᴇ sᴜʙ ᴄʜᴀɴɴᴇʟ  
<b>›› /listchnl :</b> ᴠɪᴇᴡ ᴀᴅᴅᴇᴅ ᴄʜᴀɴɴᴇʟs  
<b>›› /fsub_mode :</b> ᴛᴏɢɢʟᴇ ꜰᴏʀᴄᴇ sᴜʙ ᴍᴏᴅᴇ  
<b>›› /pbroadcast :</b> sᴇɴᴅ ᴘʜᴏᴛᴏ ᴛᴏ ᴀʟʟ ᴜꜱᴇʀs  
<b>›› /add_admin :</b> ᴀᴅᴅ ᴀɴ ᴀᴅᴍɪɴ  
<b>›› /deladmin :</b> ʀᴇᴍᴏᴠᴇ ᴀɴ ᴀᴅᴍɪɴ  
<b>›› /admins :</b> ɢᴇᴛ ʟɪsᴛ ᴏꜰ ᴀᴅᴍɪɴs
"""

    BOT_STATS_TEXT = "<b>BOT UPTIME</b>\n{uptime}"

    # ✅ Custom Caption from environment
    CUSTOM_CAPTION = os.getenv("CUSTOM_CAPTION", None)
