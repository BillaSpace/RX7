from pyrogram import filters, raw
from pyrogram.types import Message
from pyrogram.raw.types import UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupParticipants, GetGroupCall
from Opus.core.call import Anony
from Opus import app
from Opus.utils.database import get_active_chats
import asyncio

vc_participants = {}
infovc_enabled = {}

@app.on_message(filters.command("infovc") & filters.group)
async def toggle_vc_status(_, message: Message):
    chat_id = message.chat.id
    current = infovc_enabled.get(chat_id, True)
    infovc_enabled[chat_id] = not current
    await message.reply_text(
        f"🔁 Voice Chat tracking is now {'enabled ✅' if not current else 'disabled ❌'}."
    )


@Anony.userbot1.on_raw_update()
async def handle_groupcall_participants(client, update, users, chats):
    if not isinstance(update, UpdateGroupCallParticipants):
        return

    try:
        # STEP 1: Get chat_id from update.call via active chat match
        chat_id = None
        active_chats = await get_active_chats()

        for active_chat in active_chats:
            try:
                gc = await client.send(GetGroupCall(peer=await client.resolve_peer(active_chat)))
                if gc.call.id == update.call.id:
                    chat_id = active_chat
                    break
            except Exception as e:
                continue

        if not chat_id:
            print("[VC DEBUG] No active chat matched update.call.id")
            return

        if not infovc_enabled.get(chat_id, True):
            print(f"[VC DEBUG] Tracking disabled for {chat_id}")
            return

        # STEP 2: Fetch current VC participants
        try:
            response = await client.send(GetGroupParticipants(call=update.call, ids=[]))
            current = set(p.peer.user_id for p in response.participants)
        except Exception as e:
            print(f"[VC DEBUG] GetGroupParticipants failed: {e}")
            return

        # STEP 3: Compare with previous participants
        old = vc_participants.get(chat_id, set())
        joined = current - old
        left = old - current
        vc_participants[chat_id] = current

        print(f"[VC DEBUG] Chat {chat_id}: {len(joined)} joined, {len(left)} left")

        for user_id in joined:
            try:
                user = await client.get_users(user_id)
                await client.send_message(
                    chat_id,
                    f"🎉 #JoinVideoChat 🎉\n\n**Name**: {user.mention}\n**Action**: Joined",
                )
            except Exception as e:
                print(f"[VC JOIN ERROR] {user_id} in {chat_id}: {e}")

        for user_id in left:
            try:
                user = await client.get_users(user_id)
                await client.send_message(
                    chat_id,
                    f"😕 #LeftVideoChat 😕\n\n**Name**: {user.mention}\n**Action**: Left",
                )
            except Exception as e:
                print(f"[VC LEFT ERROR] {user_id} in {chat_id}: {e}")

    except Exception as e:
        print(f"[RAW UPDATE ERROR] {e}")
