import asyncio
import logging
from Opus.misc import db
from Opus.utils.database import get_active_chats, is_music_playing
from Opus.core.call import Anony

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("seek.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def timer():
    while True:
        active_chats = await get_active_chats()
        logger.info(f"Retrieved {len(active_chats)} active chats")
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing:
                    continue
                duration = playing[0]["seconds"]
                # Convert played to int to handle string values
                played = int(playing[0]["played"]) if isinstance(playing[0]["played"], (str, int)) else 0
                logger.debug(f"Chat {chat_id}: db state - played: {played}, duration: {duration}, file: {playing[0]['file']}")
                if played >= duration:
                    await Anony.change_stream(chat_id)
                else:
                    db[chat_id][0]["played"] = played + 1
            except Exception as e:
                logger.error(f"Error processing chat {chat_id}: {str(e)}", exc_info=True)
        await asyncio.sleep(1)

asyncio.create_task(timer())
