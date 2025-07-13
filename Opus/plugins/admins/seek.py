import asyncio
import logging
from Opus.misc import db
from Opus.utils.database import get_active_chats, is_music_playing, group_assistant
from Opus.core.call import Anony

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("seek_admins.log"),  # Separate log file to avoid clutter
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
                    logger.debug(f"Chat {chat_id}: Music not playing, skipping")
                    continue

                playing = db.get(chat_id)
                if not playing:
                    logger.debug(f"Chat {chat_id}: No playing data in db, skipping")
                    continue

                duration = playing[0]["seconds"]
                speed = playing[0].get("speed", 1.0)

                # Safely convert "played" field to seconds
                raw_played = playing[0]["played"]
                if isinstance(raw_played, int):
                    played = raw_played
                elif isinstance(raw_played, str) and ":" in raw_played:
                    try:
                        mins, secs = map(int, raw_played.strip().split(":"))
                        played = mins * 60 + secs
                    except ValueError:
                        logger.error(f"Chat {chat_id}: Invalid played format: {raw_played}")
                        played = 0
                elif isinstance(raw_played, str) and raw_played.isdigit():
                    played = int(raw_played)
                else:
                    logger.error(f"Chat {chat_id}: Unrecognized played format: {raw_played}")
                    played = 0

                # Adjust played time for speed
                adjusted_duration = int(playing[0]["old_second"] / speed) if playing[0].get("old_second") else duration
                logger.debug(f"Chat {chat_id}: db state - played: {played}, adjusted_duration: {adjusted_duration}, original_duration: {duration}, file: {playing[0]['file']}, speed: {speed}")

                if played >= adjusted_duration:
                    assistant = await group_assistant(Anony, chat_id)
                    await Anony.change_stream(assistant, chat_id)
                    logger.info(f"Chat {chat_id}: Successfully processed stream change")
                else:
                    # Only update played in one timer to avoid conflicts
                    if not playing[0].get("seeker_updated", False):
                        db[chat_id][0]["played"] = played + 1
                        db[chat_id][0]["seeker_updated"] = True

            except Exception as e:
                logger.error(f"Error processing chat {chat_id}: {str(e)}", exc_info=True)

        await asyncio.sleep(1)

asyncio.create_task(timer())
