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

                # Safely convert "played" field to seconds
                raw_played = playing[0]["played"]
                if isinstance(raw_played, int):
                    played = raw_played
                elif isinstance(raw_played, str) and ":" in raw_played:
                    try:
                        mins, secs = map(int, raw_played.strip().split(":"))
                        played = mins * 60 + secs
                    except ValueError:
                        played = 0
                elif isinstance(raw_played, str) and raw_played.isdigit():
                    played = int(raw_played)
                else:
                    played = 0

                logger.debug(f"Chat {chat_id}: db state - played: {played}, duration: {duration}, file: {playing[0]['file']}")

                if played >= duration:
                    await Anony.change_stream(chat_id)
                else:
                    db[chat_id][0]["played"] = played + 1

            except Exception as e:
                logger.error(f"Error processing chat {chat_id}: {str(e)}", exc_info=True)

        await asyncio.sleep(1)

asyncio.create_task(timer())
