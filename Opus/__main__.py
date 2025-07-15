import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from Opus import LOGGER, app, userbot
from Opus.core.call import Anony
from Opus.misc import sudo
from Opus.plugins import ALL_MODULES
from Opus.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        return

    try:
        await sudo()

        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception as e:
        LOGGER(__name__).warning(f"Error fetching banned users: {e}")

    try:
        await app.start()
        for all_module in ALL_MODULES:
            importlib.import_module("Opus.plugins" + all_module)
        LOGGER("Opus.plugins").info("Successfully Imported Modules...")

        await userbot.start()
        await Anony.start()

        try:
            await Anony.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
        except NoActiveGroupCall:
            LOGGER("Opus").error(
                "Please turn on the videochat of your log group/channel.\nStopping Bot..."
            )
            return
        except Exception as ex:
            LOGGER("Opus").warning(f"Stream warmup failed: {type(ex).__name__}")

        await Anony.decorators()
        LOGGER("Opus").info(
            "Vortex Music Bot Started Successfully.\nDon't forget to visit @BillaSpace"
        )

        await idle()

    except Exception as err:
        LOGGER("Opus").error(f"Fatal error during startup: {err}")

    finally:
        if app.is_connected:
            await app.stop()
        if userbot.is_connected:
            await userbot.stop()
        LOGGER("Opus").info("Stopping Opus Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
