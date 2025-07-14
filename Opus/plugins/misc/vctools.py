import asyncio
from pyrogram import filters, raw
from pyrogram.types import Message
from pyrogram.raw.types import (
    UpdateGroupCall,
    UpdateGroupCallParticipants,
    InputGroupCall
)
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from Opus import app, LOGGER
from Opus.core.call import Anony
from Opus.utils.database import (
    get_active_chats,
    get_active_video_chats,
    is_active_video_chat,
)
from datetime import datetime

vc_participants = {}
infovc_enabled = {}


@app.on_message(filters.command("infovc") & filters.group)
async def infovc_toggle(_, message: Message):
    chat_id = message.chat.id
    text = message.text.strip().lower()

    if text.endswith("on"):
        infovc_enabled[chat_id] = True
    elif text.endswith("off"):
        infovc_enabled[chat_id] = False
    else:
        infovc_enabled[chat_id] = not infovc_enabled.get(chat_id, False)

    LOGGER(__name__).info(f"[INFOVC] Chat {chat_id} tracking set to {infovc_enabled[chat_id]}")
    await message.reply_text(
        f"🔁 Voice Chat tracking is now {'enabled ✅' if infovc_enabled[chat_id] else 'disabled ❌'}."
    )


@Anony.userbot1.on_raw_update()
async def groupcall_listener(client, update, users, chats):
    try:
        # 🎬 VC Started / Ended
        if isinstance(update, UpdateGroupCall):
            LOGGER(__name__).debug("[VC DEBUG] UpdateGroupCall triggered")
            await handle_vc_status(client, update)
            return

        # 👤 VC Participants Join/Leave
        if isinstance(update, UpdateGroupCallParticipants):
            LOGGER(__name__).debug("[VC DEBUG] UpdateGroupCallParticipants triggered")
            await handle_participant_change(client, update)
            return

    except Exception as e:
        LOGGER(__name__).error(f"[RAW UPDATE ERROR] {e}")


async def handle_vc_status(client, update):
    try:
        active_chats = await get_active_video_chats()
        for chat_id in active_chats:
            try:
                gc = await client.send(GetGroupCall(peer=await client.resolve_peer(chat_id)))
                if gc.call.id == update.call.id:
                    if getattr(update.call, "schedule_date", None):
                        LOGGER(__name__).info(f"[VC DEBUG] VC scheduled in {chat_id}")
                    elif update.call.duration == 0:
                        LOGGER(__name__).info(f"[VC EVENT] VC Started in {chat_id}")
                        await client.send_message(chat_id, "🔴 **Voice Chat Started**")
                    else:
                        LOGGER(__name__).info(f"[VC EVENT] VC Ended in {chat_id}")
                        await client.send_message(chat_id, "⚪️ **Voice Chat Ended**")
                    return
            except Exception as e:
                LOGGER(__name__).warning(f"[VC DEBUG] Could not match VC ID in {chat_id}: {e}")
    except Exception as e:
        LOGGER(__name__).error(f"[VC STATUS ERROR] {e}")


async def handle_participant_change(client, update):
    try:
        chat_id = None
        active_chats = await get_active_video_chats()

        for active_chat in active_chats:
            try:
                gc = await client.send(GetGroupCall(peer=await client.resolve_peer(active_chat)))
                if gc.call.id == update.call.id:
                    chat_id = active_chat
                    break
            except Exception as e:
                LOGGER(__name__).debug(f"[VC DEBUG] Matching call failed in {active_chat}: {e}")

        if not chat_id:
            LOGGER(__name__).warning("[VC DEBUG] No active chat matched update.call.id")
            return

        if not infovc_enabled.get(chat_id, False):
            LOGGER(__name__).info(f"[VC DEBUG] Tracking disabled for {chat_id}")
            return

        input_call = InputGroupCall(id=update.call.id, access_hash=update.call.access_hash)

        current = set()
        offset = ""
        while True:
            result = await client.send(GetGroupParticipants(call=input_call, ids=[], offset=offset, limit=100))
            current.update(p.peer.user_id for p in result.participants)
            if not result.next_offset:
                break
            offset = result.next_offset

        old = vc_participants.get(chat_id, set())
        joined = current - old
        left = old - current
        vc_participants[chat_id] = current

        LOGGER(__name__).info(f"[VC DEBUG] Chat {chat_id}: {len(joined)} joined, {len(left)} left")

        for user_id in joined:
            try:
                user = await client.get_users(user_id)
                await client.send_message(chat_id, f"🎉 #JoinVC\n**Name:** {user.mention}\n**Action:** Joined VC")
            except Exception as e:
                LOGGER(__name__).warning(f"[VC JOIN ERROR] {user_id} in {chat_id}: {e}")

        for user_id in left:
            try:
                user = await client.get_users(user_id)
                await client.send_message(chat_id, f"👋 #LeftVC\n**Name:** {user.mention}\n**Action:** Left VC")
            except Exception as e:
                LOGGER(__name__).warning(f"[VC LEFT ERROR] {user_id} in {chat_id}: {e}")

    except Exception as e:
        LOGGER(__name__).error(f"[VC PARTICIPANT ERROR] {e}")
