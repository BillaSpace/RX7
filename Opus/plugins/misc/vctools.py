import asyncio
from pyrogram import filters, raw
from pyrogram.types import Message
from pyrogram.raw.types import UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupParticipants, GetGroupCall

from Opus import app
from Opus.core.call import Anony
from Opus.utils.database import (
    get_active_video_chats,
    is_active_video_chat,
)
from Opus import LOGGER

vc_participants = {}
infovc_enabled = {}


@app.on_message(filters.command("infovc") & filters.group)
async def set_vc_status(_, message: Message):
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) < 2:
        status = infovc_enabled.get(chat_id, False)
        return await message.reply_text(
            f"🔍 Voice Chat tracking is currently {'enabled ✅' if status else 'disabled ❌'}.\n"
            f"Use `/infovc on` or `/infovc off` to change it.",
            quote=True,
        )

    arg = args[1].lower()

    if arg in ["on", "enable"]:
        infovc_enabled[chat_id] = True
        await message.reply_text("✅ Voice Chat tracking has been **enabled**.", quote=True)
        LOGGER(__name__).info(f"[INFOVC] Chat {chat_id} tracking set to True")

    elif arg in ["off", "disable"]:
        infovc_enabled[chat_id] = False
        await message.reply_text("❌ Voice Chat tracking has been **disabled**.", quote=True)
        LOGGER(__name__).info(f"[INFOVC] Chat {chat_id} tracking set to False")

    else:
        await message.reply_text(
            "⚠️ Invalid command.\nUse `/infovc on` or `/infovc off`.",
            quote=True,
        )


@Anony.userbot1.on_raw_update()
async def handle_groupcall_participants(client, update, users, chats):
    if not isinstance(update, UpdateGroupCallParticipants):
        return

    try:
        active_chats = await get_active_video_chats()
        chat_id = None

        # Match the update.call.id with each active VC chat
        for active_chat in active_chats:
            try:
                resolved = await client.resolve_peer(active_chat)
                group_call = await client.send(GetGroupCall(peer=resolved))
                if group_call.call.id == update.call.id:
                    chat_id = active_chat
                    break
            except Exception as e:
                continue

        if not chat_id:
            LOGGER(__name__).debug("[VC DEBUG] No active chat matched update.call.id")
            return

        if not infovc_enabled.get(chat_id, False):
            LOGGER(__name__).debug(f"[VC DEBUG] Tracking disabled for {chat_id}")
            return

        try:
            result = await client.send(GetGroupParticipants(call=update.call, ids=[]))
            current = set(p.peer.user_id for p in result.participants)
        except Exception as e:
            LOGGER(__name__).error(f"[VC DEBUG] GetGroupParticipants failed: {e}")
            return

        old = vc_participants.get(chat_id, set())
        joined = current - old
        left = old - current
        vc_participants[chat_id] = current

        LOGGER(__name__).info(f"[VC DEBUG] Chat {chat_id}: {len(joined)} joined, {len(left)} left")

        for user_id in joined:
            try:
                user = await client.get_users(user_id)
                await client.send_message(
                    chat_id,
                    f"🎉 #JoinVideoChat 🎉\n\n**Name**: {user.mention}\n**Action**: Joined",
                )
            except Exception as e:
                LOGGER(__name__).warning(f"[VC JOIN ERROR] {user_id} in {chat_id}: {e}")

        for user_id in left:
            try:
                user = await client.get_users(user_id)
                await client.send_message(
                    chat_id,
                    f"😕 #LeftVideoChat 😕\n\n**Name**: {user.mention}\n**Action**: Left",
                )
            except Exception as e:
                LOGGER(__name__).warning(f"[VC LEFT ERROR] {user_id} in {chat_id}: {e}")

    except Exception as e:
        LOGGER(__name__).error(f"[RAW UPDATE ERROR] {e}")
