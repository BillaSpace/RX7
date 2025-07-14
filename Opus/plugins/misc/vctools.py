import asyncio
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.raw.types import InputGroupCall
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants

from Opus import app
from Opus.core.call import Anony
from Opus.core.call import group_assistant
from Opus.utils.database import get_active_chats
from config import BANNED_USERS

infovc_enabled = True
vc_participants = {}

@app.on_message(filters.command("infovc", prefixes=["/"]) & ~filters.bot)
async def toggle_infovc(_, message: Message):
    global infovc_enabled
    args = message.command
    if len(args) == 2 and args[1].lower() in ["on", "off"]:
        infovc_enabled = args[1].lower() == "on"
        status = "enabled ✅" if infovc_enabled else "disabled 🔕"
        await message.reply_text(f"VC participant tracking {status}")
    else:
        await message.reply_text("Usage: /infovc on or /infovc off")

def format_change(user, action: str):
    name = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
    mention = f"[{name}](tg://user?id={user.id})"
    return f"🎙️ **Voice Chat Update**\n👤 {mention}\n📌 **Action:** `{action}`"

async def monitor_voice_chats():
    await asyncio.sleep(1)  # Initial delay
    print("[VC Monitor] Started monitoring voice chats.")
    while True:
        if not infovc_enabled:
            await asyncio.sleep(1)
            continue

        try:
            active_chats = await get_active_chats()
        except Exception as e:
            print(f"[VC Monitor] Error fetching active chats: {e}")
            active_chats = []

        for chat_id in active_chats:
            try:
                assistant = await group_assistant(Anony, chat_id)
                if not assistant:
                    continue

                # Get active group call
                active_call = await Anony.get_call(chat_id)
                if not active_call:
                    continue

                call = await assistant.invoke(
                    GetGroupCall(call=InputGroupCall(id=active_call.id, access_hash=active_call.access_hash))
                )
                call = call.call

                result = await assistant.invoke(
                    GetGroupParticipants(call=InputGroupCall(id=call.id, access_hash=call.access_hash), ids=[])
                )
                new_ids = [p.user_id for p in result.participants]
                old_ids = vc_participants.get(chat_id, [])
                joined = [i for i in new_ids if i not in old_ids]
                left = [i for i in old_ids if i not in new_ids]

                for uid in joined:
                    try:
                        user = await app.get_users(uid)
                        msg = await app.send_message(chat_id, format_change(user, "Joined"), parse_mode="markdown")
                        await asyncio.sleep(0.5)
                        await msg.delete()
                    except Exception as e:
                        print(f"[VC Monitor] Error sending join message: {e}")

                for uid in left:
                    try:
                        user = await app.get_users(uid)
                        msg = await app.send_message(chat_id, format_change(user, "Left"), parse_mode="markdown")
                        await asyncio.sleep(0.5)
                        await msg.delete()
                    except Exception as e:
                        print(f"[VC Monitor] Error sending leave message: {e}")

                vc_participants[chat_id] = new_ids

            except Exception as e:
                print(f"[VC Monitor] Error in chat {chat_id}: {e}")
                continue

        await asyncio.sleep(5)

# Start monitor loop after app is started
async def start_vc_monitor(_: "Client"):
    asyncio.create_task(monitor_voice_chats())
