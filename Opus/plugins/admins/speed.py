from pyrogram import filters
from pyrogram.types import Message
from pyrogram.types import CallbackQuery
from Opus import app
from Opus.core.call import Anony
from Opus.misc import SUDOERS, db
from Opus.utils import AdminRightsCheck
from Opus.utils.decorators.language import languageCB
from Opus.utils.inline import close_markup, speed_markup
from config import BANNED_USERS, adminlist
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("speed.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

checker = []

@app.on_message(
    filters.command(["cspeed", "speed", "cslow", "slow", "playback", "cplayback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def playback(cli, message: Message, _, chat_id):
    logger.debug(f"Received playback command in chat {chat_id} from user {message.from_user.id}")
    playing = db.get(chat_id)
    if not playing:
        logger.error(f"Chat {chat_id}: No playing data in db")
        return await message.reply_text(_["queue_2"])
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        logger.error(f"Chat {chat_id}: Duration is 0")
        return await message.reply_text(_["admin_27"])
    file_path = playing[0]["file"]
    if "downloads" not in file_path:
        logger.error(f"Chat {chat_id}: File path {file_path} does not contain 'downloads'")
        return await message.reply_text(_["admin_27"])
    upl = speed_markup(_, chat_id)
    await message.reply_text(
        text=_["admin_28"].format(app.mention),
        reply_markup=upl,
    )
    logger.info(f"Chat {chat_id}: Displayed speed markup")

@app.on_callback_query(filters.regex("SpeedUP") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    try:
        chat, speed = callback_data.split(None, 1)[1].split("|")
        chat_id = int(chat)
        speed = float(speed)  # Convert to float for validation
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data: {callback_data}")
        return await CallbackQuery.answer("Invalid speed data", show_alert=True)

    logger.debug(f"Received SpeedUP callback in chat {chat_id} with speed {speed} from user {CallbackQuery.from_user.id}")

    if not await is_active_chat(chat_id):
        logger.error(f"Chat {chat_id}: Not an active chat")
        return await CallbackQuery.answer(_["general_5"], show_alert=True)

    is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
    if not is_non_admin:
        if CallbackQuery.from_user.id not in SUDOERS:
            admins = adminlist.get(CallbackQuery.message.chat.id)
            if not admins:
                logger.error(f"Chat {chat_id}: No admins found")
                return await CallbackQuery.answer(_["admin_13"], show_alert=True)
            if CallbackQuery.from_user.id not in admins:
                logger.error(f"Chat {chat_id}: User {CallbackQuery.from_user.id} is not an admin")
                return await CallbackQuery.answer(_["admin_14"], show_alert=True)

    playing = db.get(chat_id)
    if not playing:
        logger.error(f"Chat {chat_id}: No playing data in db")
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)

    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        logger.error(f"Chat {chat_id}: Duration is 0")
        return await CallbackQuery.answer(_["admin_27"], show_alert=True)

    file_path = playing[0]["file"]
    if "downloads" not in file_path:
        logger.error(f"Chat {chat_id}: File path {file_path} does not contain 'downloads'")
        return await CallbackQuery.answer(_["admin_27"], show_alert=True)

    # Validate speed
    valid_speeds = [0.5, 0.75, 1.0, 1.5, 2.0]
    if speed not in valid_speeds:
        logger.error(f"Chat {chat_id}: Invalid speed value: {speed}")
        return await CallbackQuery.answer(f"Invalid speed: {speed}. Valid options are {valid_speeds}", show_alert=True)

    checkspeed = playing[0].get("speed")
    if checkspeed and str(checkspeed) == str(speed):
        logger.debug(f"Chat {chat_id}: Speed {speed} already set")
        return await CallbackQuery.answer(
            _["admin_29"] if speed == 1.0 else f"Speed is already set to {speed}x",
            show_alert=True,
        )

    if chat_id in checker:
        logger.warning(f"Chat {chat_id}: Speed change already in progress")
        return await CallbackQuery.answer(_["admin_30"], show_alert=True)

    checker.append(chat_id)
    try:
        await CallbackQuery.answer("Processing speed change...")
        mystic = await CallbackQuery.edit_message_text(
            text=_["admin_32"].format(CallbackQuery.from_user.mention),
        )
        try:
            await Anony.speedup_stream(
                chat_id,
                file_path,
                speed,
                playing,
            )
            logger.info(f"Chat {chat_id}: Successfully changed speed to {speed}x")
        except Exception as e:
            logger.error(f"Chat {chat_id}: Failed to change speed: {str(e)}", exc_info=True)
            if chat_id in checker:
                checker.remove(chat_id)
            await mystic.edit_text(_["admin_33"], reply_markup=close_markup(_))
            return
        if chat_id in checker:
            checker.remove(chat_id)
        await mystic.edit_text(
            text=_["admin_34"].format(speed, CallbackQuery.from_user.mention),
            reply_markup=close_markup(_),
        )
    except Exception as e:
        logger.error(f"Chat {chat_id}: Callback processing failed: {str(e)}", exc_info=True)
        if chat_id in checker:
            checker.remove(chat_id)
        await CallbackQuery.edit_message_text(_["admin_33"], reply_markup=close_markup(_))
