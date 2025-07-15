import asyncio
import signal
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode
import config
from ..logging import LOGGER

class Anony(Client):
    def __init__(self):
        LOGGER(__name__).info(f"Sᴛᴀʀᴛɪɴɢ Sᴛᴏʀᴍ Mᴜsɪᴄ Bᴀʙʏ...")
        super().__init__(
            name="Opus",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            parse_mode=ParseMode.HTML,
            max_concurrent_transmissions=7,
        )

    async def start(self):
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name + " " + (self.me.last_name or "")
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(
                chat_id=config.LOGGER_ID,
                text=f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b><u>\n\nɪᴅ : <code>{self.id}</code>\nɴᴀᴍᴇ : {self.name}\nᴜsᴇʀɴᴀᴍᴇ : @{self.username}",
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error(
                "Sᴛᴏʀᴍ ʜᴀs ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴄᴄᴇss ᴛʜᴇ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ. Mᴀᴋᴇ sᴜʀᴇ ᴛʜᴀᴛ ʏᴏᴜ ʜᴀᴠᴇ ᴀᴅᴅᴇᴅ sᴛᴏʀᴍ ᴍᴜsɪᴄ ᴛᴏ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ."
            )
            await self.stop()  # Graceful exit instead of exit()
        except Exception as ex:
            LOGGER(__name__).error(
                f"ᴠᴏʀᴛᴇx ᴍᴜsɪᴄ ʜᴀs ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴄᴄᴇss ᴛʜᴇ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ.\n  Reason : {type(ex).__name__}."
            )
            await self.stop()  # Graceful exit instead of exit()

        a = await self.get_chat_member(config.LOGGER_ID, self.id)
        if a.status != ChatMemberStatus.ADMINISTRATOR:
            LOGGER(__name__).error(
                "ᴘʟᴇᴀsᴇ ᴘʀᴏᴍᴏᴛᴇ Sᴛᴏʀᴍ Vᴏʀᴛᴇx Mᴜsɪᴄ As ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ."
            )
            await self.stop()  # Graceful exit instead of exit()

        LOGGER(__name__).info(f"Sᴛᴏʀᴍ Mᴜsɪᴄ Sᴛᴀʀᴛᴇᴅ ᴀs {self.name}")

    async def stop(self):
        LOGGER(__name__).info(f"ɢɪᴠɪɴɢ ᴀ ʀᴇsᴛ ᴛᴏ sᴛᴏʀᴍ...")
        await super().stop()


# Function to handle shutdown when Ctrl+C is pressed
def handle_shutdown_signal(loop, bot):
    print("Gʀᴀᴄᴇғᴜʟʟʏ sʜᴜᴛᴛɪɴɢ ᴅᴏᴡɴ...")
    loop.stop()  # Stop the event loop
    asyncio.create_task(bot.stop())  # Stop the bot gracefully

# Main entry point to run the bot
if __name__ == "__main__":
    bot = Anony()

    loop = asyncio.get_event_loop()

    # Register signal handler for SIGINT (Ctrl+C)
    loop.add_signal_handler(signal.SIGINT, handle_shutdown_signal, loop, bot)

    try:
        # Start the bot
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        print("sᴛᴏʀᴍ ɪs ᴍᴀɴɪᴘᴜʟᴀᴛᴇᴅ. Exɪᴛɪɴɢ...")
    finally:
        loop.close()  # Ensure the loop is closed after shutdown
