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

        # ✅ Get bot info after starting
        self.me = await self.get_me()
        self.id = self.me.id
        self.name = f"{self.me.first_name} {(self.me.last_name or '')}".strip()
        self.username = self.me.username
        self.mention = self.me.mention

        # ✅ Attempt sending to LOGGER group
        try:
            await self.send_message(
                chat_id=config.LOGGER_ID,
                text=f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b></u>\n\n"
                     f"ɪᴅ : <code>{self.id}</code>\nɴᴀᴍᴇ : {self.name}\nᴜsᴇʀɴᴀᴍᴇ : @{self.username}",
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error(
                "Sᴛᴏʀᴍ ʜᴀs ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴄᴄᴇss ᴛʜᴇ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ. Mᴀᴋᴇ sᴜʀᴇ ᴛʜᴀᴛ ʏᴏᴜ ʜᴀᴠᴇ ᴀᴅᴅᴇᴅ sᴛᴏʀᴍ ᴍᴜsɪᴄ ᴛᴏ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ."
            )
            return await self.stop()

        except Exception as ex:
            LOGGER(__name__).error(
                f"ᴠᴏʀᴛᴇx ᴍᴜsɪᴄ ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴍᴇssᴀɢᴇ ᴛᴏ ʟᴏɢ ɢʀᴏᴜᴘ.\nReason: {type(ex).__name__}"
            )
            return await self.stop()

        # ✅ Check if bot is admin in LOGGER_ID
        try:
            chat_member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if chat_member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error(
                    "ᴘʟᴇᴀsᴇ ᴘʀᴏᴍᴏᴛᴇ Sᴛᴏʀᴍ Vᴏʀᴛᴇx Mᴜsɪᴄ ᴀs ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ."
                )
                return await self.stop()
        except Exception as e:
            LOGGER(__name__).error(f"ғᴀɪʟᴇᴅ ᴛᴏ ᴄʜᴇᴄᴋ ʟᴏɢ ɢʀᴏᴜᴘ sᴛᴀᴛᴜs: {e}")
            return await self.stop()

        LOGGER(__name__).info(f"Sᴛᴏʀᴍ Mᴜsɪᴄ Sᴛᴀʀᴛᴇᴅ ᴀs {self.name}")

    async def stop(self):
        LOGGER(__name__).info("ɢɪᴠɪɴɢ ᴀ ʀᴇsᴛ ᴛᴏ sᴛᴏʀᴍ...")
        await super().stop()


# Optional signal handler (not necessary on all deployments)
def handle_shutdown_signal(loop, bot):
    print("Gʀᴀᴄᴇғᴜʟʟʏ sʜᴜᴛᴛɪɴɢ ᴅᴏᴡɴ...")
    loop.stop()
    asyncio.create_task(bot.stop())


# Entrypoint for direct execution (if used)
if __name__ == "__main__":
    bot = Anony()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, handle_shutdown_signal, loop, bot)

    try:
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        print("sᴛᴏʀᴍ ɪs ᴍᴀɴɪᴘᴜʟᴀᴛᴇᴅ. Exɪᴛɪɴɢ...")
    finally:
        loop.close()
