from pyrogram import raw
from pyrogram.raw.types import UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from Opus.core.call import Anony
from pyrogram import filters
from pyrogram.types import Message

# Global state for tracking VC and toggle
infovc_enabled = {}    # {chat_id: True/False}
vc_participants = {}   # {chat_id: set(user_ids)}


# Command to toggle /infovc
@Anony.userbot1.on_message(filters.command("infovc") & filters.group)
async def toggle_vc_status(_, message: Message):
    chat_id = message.chat.id
    current = infovc_enabled.get(chat_id, True)
    infovc_enabled[chat_id] = not current
    await message.reply_text(
        f"🔁 Voice Chat participant tracking is now {'enabled ✅' if not current else 'disabled ❌'}."
    )
    print(f"[INFOVC] Chat {chat_id} tracking set to {not current}")


# Raw VC participant updates
@Anony.userbot1.on_raw_update()
async def handle_groupcall_participants(client, update, users, chats):
    if not isinstance(update, UpdateGroupCallParticipants):
        return

    try:
        if not chats:
            print("[VC DEBUG] No chat in update")
            return
        chat_id = list(chats.values())[0].id

        # Respect /infovc toggle (default: on)
        if not infovc_enabled.get(chat_id, True):
            print(f"[VC DEBUG] Skipped (disabled): {chat_id}")
            return

        # Fetch group call metadata
        try:
            call_info = await client.send(GetGroupCall(call=update.call, limit=1))
        except Exception as e:
            print(f"[VC DEBUG] GetGroupCall failed: {e}")
            return

        # Get list of participants
        try:
            response = await client.send(GetGroupParticipants(call=update.call, ids=[]))
            current = set(p.peer.user_id for p in response.participants)
        except Exception as e:
            print(f"[VC DEBUG] GetGroupParticipants failed: {e}")
            return

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
