from pyrogram import filters
from pyrogram.types import Message
from typing import Union, List
import asyncio

from Opus import app
from Opus.core.call import Anony

# Toggle VC join/leave notifications
infovc_enabled = True

def command(commands: Union[str, List[str]]):
    return filters.command(commands, prefixes=["/"])

@app.on_message(command(["infovc"]))
async def toggle_infovc(_, message: Message):
    global infovc_enabled
    if len(message.command) > 1:
        state = message.command[1].lower()
        if state == "on":
            infovc_enabled = True
            await message.reply("✅ VC participants join/leave notifications Are enabled Now.")
        elif state == "off":
            infovc_enabled = False
            await message.reply("🔕 VC join/leave notifications Are disabled Now.")
        else:
            await message.reply("⚠️ Usage: /infovc on or /infovc off")
    else:
        await message.reply("⚙️ Usage: /infovc on or /infovc off")

# Format message
def format_user(user, action: str):
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    return (
        "**🎙️ Voice Chat Update**\n"
        f"**👤 User**: [{full_name}](tg://user?id={user.id})\n"
        f"**🔗 Username**: @{user.username if user.username else 'N/A'}\n"
        f"**🎯 Action**: {action}"
    )

# Use on_participants_change instead of joined/left
@Anony.on_participants_change()
async def vc_participants_change(_, chat_id: int, joined: list, left: list):
    if not infovc_enabled:
        return

    try:
        # Handle joins
        for user in joined:
            u = user.user
            msg = await app.send_message(chat_id, format_user(u, "Joined"))
            await asyncio.sleep(1)
            await msg.delete()

        # Handle leaves
        for user in left:
            u = user.user
            msg = await app.send_message(chat_id, format_user(u, "Left"))
            await asyncio.sleep(1)
            await msg.delete()

    except Exception as e:
        print(f"[VC PARTICIPANT ERROR] in {chat_id} — {e}")
