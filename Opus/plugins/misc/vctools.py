import asyncio
from pyrogram import Client, filters, raw
from pyrogram.types import Message
from pyrogram.raw.types import UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from pyrogram.raw.types import InputGroupCall
from Opus import app

# Cache for participant tracking per chat
vc_participants = {}  # chat_id -> set(user_id)
# VC tracking toggle per chat (default True)
infovc_enabled_chats = {}  # chat_id -> True/False

# Toggle command: /infovc
@app.on_message(filters.command("infovc") & filters.group)
async def toggle_infovc(client: Client, message: Message):
    chat_id = message.chat.id
    current = infovc_enabled_chats.get(chat_id, True)  # default enabled
    infovc_enabled_chats[chat_id] = not current
    status = "enabled ✅" if not current else "disabled ❌"
    await message.reply_text(
        f"Voice Chat join/leave tracking is now **{status}**.",
        quote=True
    )

# Raw update handler for VC participant tracking
@app.on_raw_update()
async def handle_video_chat_participants(client: Client, update, users, chats):
    if not isinstance(update, UpdateGroupCallParticipants):
        return

    try:
        # Extract chat_id from chats map (fallback guess)
        if not chats:
            return
        chat_id = list(chats.values())[0].id

        # Respect toggle setting (default: enabled)
        if not infovc_enabled_chats.get(chat_id, True):
            return

        # Fetch group call object
        call_info = await client.send(
            GetGroupCall(call=update.call, limit=1)
        )

        # Fetch current participants
        result = await client.send(
            GetGroupParticipants(call=update.call, ids=[])
        )

        current_users = set(p.peer.user_id for p in result.participants)
        old_users = vc_participants.get(chat_id, set())

        # Compare old vs new
        joined = current_users - old_users
        left = old_users - current_users

        # Update cache
        vc_participants[chat_id] = current_users

        # Announce joined
        for user_id in joined:
            try:
                user = await client.get_users(user_id)
                text = (
                    f"🎉 #JoinVideoChat 🎉\n\n"
                    f"Name : {user.mention}\n"
                    f"Action : Joined\n\n"
                )
                await client.send_message(chat_id, text)
            except Exception as e:
                print(f"Error announcing join: {e}")

        # Announce left
        for user_id in left:
            try:
                user = await client.get_users(user_id)
                text = (
                    f"#LeftVideoChat😕\n\n"
                    f"Name : {user.mention}\n"
                    f"Action : Left\n\n"
                )
                await client.send_message(chat_id, text)
            except Exception as e:
                print(f"Error announcing leave: {e}")

    except Exception as e:
        print(f"VC tracking error: {e}")
