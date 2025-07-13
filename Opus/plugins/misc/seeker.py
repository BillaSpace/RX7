import asyncio
import logging

from Opus.misc import db
from Opus.utils.database import get_active_chats, is_music_playing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("seeker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def timer():
    try:
        while not await asyncio.sleep(1):
            active_chats = await get_active_chats()
            logger.info(f"Retrieved {len(active_chats)} active chats")
            for chat_id in active_chats:
                try:
                    if not await is_music_playing(chat_id):
                        logger.debug(f"Chat {chat_id}: Music not playing, skipping")
                        continue
                    playing = db.get(chat_id)
                    if not playing:
                        logger.warning(f"Chat {chat_id}: No playing data found")
                        continue
                    duration = int(playing[0]["seconds"])
                    if duration == 0:
                        logger.warning(f"Chat {chat_id}: Duration is 0, skipping")
                        continue
                    if db[chat_id][0]["played"] >= duration:
                        logger.info(f"Chat {chat_id}: Playback completed (played: {db[chat_id][0]['played']}, duration: {duration})")
                        continue
                    db[chat_id][0]["played"] += 1
                    logger.debug(f"Chat {chat_id}: Incremented played time to {db[chat_id][0]['played']}")
                except Exception as e:
                    logger.error(f"Error processing chat {chat_id}: {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"Critical error in timer loop: {str(e)}", exc_info=True)

asyncio.create_task(timer())
