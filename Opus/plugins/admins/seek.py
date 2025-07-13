import logging
from pyrogram import filters
from pyrogram.types import Message

from Opus import YouTube, app
from Opus.core.call import Anony
from Opus.misc import db
from Opus.utils import AdminRightsCheck, seconds_to_min
from Opus.utils.inline import close_markup
from config import BANNED_USERS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("seek.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@app.on_message(
    filters.command(["seek", "cseek", "seekback", "cseekback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def seek_comm(cli, message: Message, _, chat_id):
    try:
        if len(message.command) == 1:
            logger.warning(f"Chat {chat_id}: No seek time provided")
            return await message.reply_text(_["admin_20"])
        
        query = message.text.split(None, 1)[1].strip()
        if not query.isnumeric():
            logger.warning(f"Chat {chat_id}: Invalid seek time format: {query}")
            return await message.reply_text(_["admin_21"])
        
        playing = db.get(chat_id)
        if not playing:
            logger.warning(f"Chat {chat_id}: No active playback found")
            return await message.reply_text(_["queue_2"])
        
        duration_seconds = int(playing[0]["seconds"])
        if duration_seconds == 0:
            logger.warning(f"Chat {chat_id}: Duration is 0")
            return await message.reply_text(_["admin_22"])
        
        file_path = playing[0]["file"]
        duration_played = int(playing[0]["played"])
        duration_to_skip = int(query)
        duration = playing[0]["dur"]
        
        logger.info(f"Chat {chat_id}: Processing seek command (played: {duration_played}, skip: {duration_to_skip})")
        
        if message.command[0][-2] == "c":
            if (duration_played - duration_to_skip) <= 10:
                logger.warning(f"Chat {chat_id}: Cannot seek back, too close to start (played: {duration_played})")
                return await message.reply_text(
                    text=_["admin_23"].format(seconds_to_min(duration_played), duration),
                    reply_markup=close_markup(_),
                )
            to_seek = duration_played - duration_to_skip + 1
        else:
            if (duration_seconds - (duration_played + duration_to_skip)) <= 10:
                logger.warning(f"Chat {chat_id}: Cannot seek forward, too close to end (remaining: {duration_seconds - duration_played})")
                return await message.reply_text(
                    text=_["admin_23"].format(seconds_to_min(duration_played), duration),
                    reply_markup=close_markup(_),
                )
            to_seek = duration_played + duration_to_skip + 1
        
        mystic = await message.reply_text(_["admin_24"])
        if "vid_" in file_path:
            n, file_path = await YouTube.video(playing[0]["vidid"], True)
            if n == 0:
                logger.error(f"Chat {chat_id}: Failed to retrieve video for seeking")
                return await message.reply_text(_["admin_22"])
        
        check = (playing[0]).get("speed_path")
        if check:
            file_path = check
        if "index_" in file_path:
            file_path = playing[0]["vidid"]
        
        try:
            await Anony.seek_stream(
                chat_id,
                file_path,
                seconds_to_min(to_seek),
                duration,
                playing[0]["streamtype"],
            )
            logger.info(f"Chat {chat_id}: Successfully sought to {seconds_to_min(to_seek)}")
        except Exception as e:
            logger.error(f"Chat {chat_id}: Failed to seek stream: {str(e)}", exc_info=True)
            return await mystic.edit_text(_["admin_26"], reply_markup=close_markup(_))
        
        if message.command[0][-2] == "c":
            db[chat_id][0]["played"] -= duration_to_skip
        else:
            db[chat_id][0]["played"] += duration_to_skip
        
        logger.info(f"Chat {chat_id}: Updated played time to {db[chat_id][0]['played']}")
        await mystic.edit_text(
            text=_["admin_25"].format(seconds_to_min(to_seek), message.from_user.mention),
            reply_markup=close_markup(_),
        )
    
    except Exception as e:
        logger.error(f"Chat {chat_id}: Critical error in seek command: {str(e)}", exc_info=True)
        await message.reply_text(_["admin_26"], reply_markup=close_markup(_))
