import asyncio
from pyrogram import Client, filters, raw
from pyrogram.types import Message
from pyrogram.raw.types import UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from pyrogram.raw.types import InputGroupCall
from Opus import app  # My initialized Client App 

# In-memory storage
vc_participants = {}           # {chat_id: set(user_ids)}
infovc_enabled_chats = {}      # {chat_id: True/False}, default = True


# /infovc toggle command
@app.on_message(filters.command("infovc") & filters.group)
async def toggle_infovc(client: Client, message: Message):
    chat_id = message.chat.id
    current = infovc_enabled_chats.get(chat_id, True)  # Default enabled
    infovc_enabled_chats[chat_id] = not current
    new_state = "enabled ✅" if not current else "disabled ❌"
    await message.reply_text(
        f"🔁 Voice Chat participant tracking is now **{new_state}**.",
        quote=True
    )
    print(f"[INFOVC] Chat {chat_id} set to {not current}")


# Voice chat participant tracker
@app.on_raw_update()
async def handle_video_chat_participants(client: Client, update, users, chats):
    try:
        if not isinstance(update, UpdateGroupCallParticipants):
            return

        # Extract chat ID
        if not chats or len(chats) == 0:
            print("[VC DEBUG] No chat info in update")
            return
        chat_id = list(chats.values())[0].id

        # Respect toggle
        if not infovc_enabled_chats.get(chat_id, True):
            print(f"[VC DEBUG] Tracking disabled in {chat_id}")
            return

        # Get group call info
        try:
            call_info = await client.send(
                GetGroupCall(call=update.call, limit=1)
            )
        except Exception as e:
            print(f"[VC DEBUG] GetGroupCall failed: {e}")
            return

        # Get current participants
        try:
            result = await client.send(
                GetGroupParticipants(call=update.call, ids=[])
            )
        except Exception as e:
            print(f"[VC DEBUG] GetGroupParticipants failed: {e}")
            return

        current_users = set(p.peer.user_id for p in result.participants)
        old_users = vc_participants.get(chat_id, set())

        joined = current_users - old_users
        left = old_users - current_users

        # Update cache
        vc_participants[chat_id] = current_users
        print(f"[VC DEBUG] Chat {chat_id}: {len(joined)} joined, {len(left)} left")

        # Notify joined users
        for user_id in joined:
            try:
                user = await client.get_users(user_id)
                text = (
                    f"🎉 #JoinVideoChat 🎉\n\n"
                    f"**Name**: {user.mention}\n"
                    f"**Action**: Joined\n"
                )
                await client.send_message(chat_id, text)
                print(f"[VC JOIN] {user_id} joined in {chat_id}")
            except Exception as e:
                print(f"[VC JOIN ERROR] user_id={user_id} in chat {chat_id}: {e}")

        # Notify left users
        for user_id in left:
            try:
                user = await client.get_users(user_id)
                text = (
                    f"😕 #LeftVideoChat 😕\n\n"
                    f"**Name**: {user.mention}\n"
                    f"**Action**: Left\n"
                )
                await client.send_message(chat_id, text)
                print(f"[VC LEFT] {user_id} left in {chat_id}")
            except Exception as e:
                print(f"[VC LEFT ERROR] user_id={user_id} in chat {chat_id}: {e}")

    except Exception as e:
        print(f"[RAW UPDATE ERROR] {e}")
