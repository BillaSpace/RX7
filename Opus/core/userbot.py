from pyrogram import Client
import config
from ..logging import LOGGER

assistants = []
assistantids = []


class Userbot(Client):
    def __init__(self):
        self.one = Client(
            name="AnonXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            name="AnonXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.three = Client(
            name="AnonXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.four = Client(
            name="AnonXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.five = Client(
            name="AnonXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )

    async def start(self):
        LOGGER(__name__).info("Starting Assistants...")

        async def _start_assistant(index: int, client: Client):
            try:
                await client.start()
                try:
                    await client.join_chat("BillaCore")
                    await client.join_chat("BillaSpace")
                except:
                    pass

                me = await client.get_me()
                client.id = me.id
                client.name = me.mention
                client.username = me.username

                assistants.append(index)
                assistantids.append(me.id)

                try:
                    await client.send_message(config.LOGGER_ID, "Assistant Started")
                except:
                    LOGGER(__name__).error(
                        f"Assistant Account {index} failed to send message to log group. Promote it!"
                    )
                    exit()

                LOGGER(__name__).info(f"Assistant {index} Started as {client.name}")

            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant {index}: {e}")
                exit()

        if config.STRING1:
            await _start_assistant(1, self.one)
        if config.STRING2:
            await _start_assistant(2, self.two)
        if config.STRING3:
            await _start_assistant(3, self.three)
        if config.STRING4:
            await _start_assistant(4, self.four)
        if config.STRING5:
            await _start_assistant(5, self.five)

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2:
                await self.two.stop()
            if config.STRING3:
                await self.three.stop()
            if config.STRING4:
                await self.four.stop()
            if config.STRING5:
                await self.five.stop()
        except Exception:
            pass
