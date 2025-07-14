import asyncio
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from pyrogram.raw.types import InputGroupCall

from Opus import app, Userbot  # Your userbot from core.userbot
from Opus.core.call import Anony  # PyTgCalls instance

# State
infovc_enabled = True
vc_participants = {}  # Stores {chat_id: [user_ids]}

# /infovc on|off toggle
@app.on_message(filters.command("infovc", prefixes=["/"]))
async def toggle_infovc(_, message: Message):
    global infovc_enabled
    args = message.command
    if len(args) == 2 and args[1].lower() in ["on", "off"]:
        infovc_enabled = args[1].lower() == "on"
        status = "enabled ✅" if infovc_enabled else "disabled 🔕"
        await message.reply(f"VC participant alerts {status}")
    else:
        await message.reply("Usage: /infovc [on/off]")

# Formatting messages
def format_change(user, action: str):
    name = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
    mention = f"[{name}](tg://user?id={user.id})"
    return f"🎙️ #Voice Chat Update\n👤 {mention}\n📌 **Action:** {action}"

# Main polling loop
async def monitor_voice_chats():
    await asyncio.sleep(1)  # Let bot warm up
    while True:
        if not infovc_enabled:
            await asyncio.sleep(1)
            continue

        for dialog in await userbot.get_dialogs():
            chat = dialog.chat
            if not (chat and chat.id):
                continue

            chat_id = chat.id
            try:
                call = await userbot.send(
                    GetGroupCall(
                        call=InputGroupCall(id=0, access_hash=0),  # placeholder
                        group_call=await Anony.get_call(chat_id)
                    )
                )
                call = call.call

                result = await userbot.send(
                    GetGroupParticipants(call=InputGroupCall(id=call.id, access_hash=call.access_hash), ids=[])
                )
                new_ids = [p.user_id for p in result.participants]

                old_ids = vc_participants.get(chat_id, [])
                joined = [i for i in new_ids if i not in old_ids]
                left = [i for i in old_ids if i not in new_ids]

                # Send messages for joins
                for uid in joined:
                    user = await app.get_users(uid)
                    msg = await app.send_message(chat_id, format_change(user, "Joined"))
                    await asyncio.sleep(1)
                    await msg.delete()

                # Send messages for leaves
                for uid in left:
                    user = await app.get_users(uid)
                    msg = await app.send_message(chat_id, format_change(user, "Left"))
                    await asyncio.sleep(1)
                    await msg.delete()

                vc_participants[chat_id] = new_ids

            except Exception as e:
                # Silently skip chats without active VC or permission
                pass

        await asyncio.sleep(5)

# Start task in background
asyncio.get_event_loop().create_task(monitor_voice_chats())
