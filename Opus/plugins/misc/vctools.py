import asyncio
from pyrogram import filters, Client
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
        print(f"[INFOVC] Tracking toggled: {status}")
        await message.reply_text(f"VC participant tracking {status}")
    else:
        await message.reply_text("Usage: /infovc on or /infovc off")

def format_change(user, action: str):
    name = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
    mention = f"[{name}](tg://user?id={user.id})"
    return f"🎙️ **Voice Chat Update**\n👤 {mention}\n📌 **Action:** `{action}`"

async def monitor_voice_chats():
    await asyncio.sleep(1)
    print("[VC Monitor] Started monitoring voice chats.")
    while True:
        if not infovc_enabled:
            await asyncio.sleep(1)
            continue

        try:
            active_chats = await get_active_chats()
            print(f"[VC Monitor] Active chats to check: {active_chats}")
        except Exception as e:
            print(f"[VC Monitor] Error fetching active chats: {e}")
            active_chats = []

        for chat_id in active_chats:
            print(f"[VC Monitor] Checking chat ID: {chat_id}")
            try:
                assistant = await group_assistant(Anony, chat_id)
                if not assistant:
                    print(f"[VC Monitor] No assistant available for chat {chat_id}")
                    continue

                active_call = await Anony.get_call(chat_id)
                if not active_call:
                    print(f"[VC Monitor] No active call in chat {chat_id}")
                    continue

                print(f"[VC Monitor] Getting call info for chat {chat_id}")
                call = await assistant.invoke(
                    GetGroupCall(call=InputGroupCall(id=active_call.id, access_hash=active_call.access_hash))
                )
                call = call.call

                print(f"[VC Monitor] Fetching participants for chat {chat_id}")
                result = await assistant.invoke(
                    GetGroupParticipants(call=InputGroupCall(id=call.id, access_hash=call.access_hash), ids=[])
                )
                new_ids = [p.user_id for p in result.participants]
                old_ids = vc_participants.get(chat_id, [])

                joined = [i for i in new_ids if i not in old_ids]
                left = [i for i in old_ids if i not in new_ids]

                if joined:
                    print(f"[VC Monitor] Users joined in {chat_id}: {joined}")
                if left:
                    print(f"[VC Monitor] Users left in {chat_id}: {left}")

                for uid in joined:
                    try:
                        user = await app.get_users(uid)
                        msg = await app.send_message(chat_id, format_change(user, "Joined"), parse_mode="markdown")
                        await asyncio.sleep(0.5)
                        await msg.delete()
                        print(f"[VC Monitor] Announced join of {uid} in {chat_id}")
                    except Exception as e:
                        print(f"[VC Monitor] Error announcing join of {uid}: {e}")

                for uid in left:
                    try:
                        user = await app.get_users(uid)
                        msg = await app.send_message(chat_id, format_change(user, "Left"), parse_mode="markdown")
                        await asyncio.sleep(0.5)
                        await msg.delete()
                        print(f"[VC Monitor] Announced leave of {uid} in {chat_id}")
                    except Exception as e:
                        print(f"[VC Monitor] Error announcing leave of {uid}: {e}")

                vc_participants[chat_id] = new_ids

            except Exception as e:
                print(f"[VC Monitor] General error in chat {chat_id}: {e}")
                continue

        await asyncio.sleep(5)

async def start_vc_monitor(_: "Client"):
    asyncio.create_task(monitor_voice_chats())
