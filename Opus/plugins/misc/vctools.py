import asyncio
import logging

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.raw.types import UpdateGroupCall, UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from pyrogram.raw.types import InputGroupCall

from Opus import app
from Opus.core.call import group_assistant
from Opus.utils.database import (
    get_active_chats,
    get_active_video_chats,
    add_active_video_chat,
    remove_active_video_chat,
)
from Opus import LOGGER

LOGGER = LOGGER(__name__)

# Per-chat toggle status
infovc_enabled = {}  # chat_id: bool
# VC participant cache
vc_participants = {}  # chat_id: set(user_ids)
# Map call.id to chat_id
call_to_chat = {}  # call_id: chat_id


@app.on_message(filters.command("vcstatus") & filters.group)
async def toggle_vc_tracking(_, message: Message):
    chat_id = message.chat.id
    status = infovc_enabled.get(chat_id, False)
    infovc_enabled[chat_id] = not status
    await message.reply_text(
        f"Voice Chat tracking **{'enabled' if not status else 'disabled'}** for this group."
    )
    LOGGER.info(f"[INFOVC] Chat {chat_id} tracking set to {not status}")


@app.on_raw_update()
async def handle_vc_updates(client, update, users, chats):
    if isinstance(update, UpdateGroupCallParticipants):
        call_id = update.call.id
        chat_id = call_to_chat.get(call_id)

        if not chat_id:
            # Try matching call.id by scanning active chats
            for cid in await get_active_chats():
                try:
                    peer = await client.resolve_peer(cid)
                    res = await client.send(GetGroupCall(peer=peer))
                    if res.call.id == call_id:
                        chat_id = cid
                        call_to_chat[call_id] = cid
                        LOGGER.info(f"[VC DEBUG] Mapped call.id {call_id} to chat {cid}")
                        break
                except Exception as e:
                    continue

        if not chat_id:
            LOGGER.warning("[VC DEBUG] No active chat matched update.call.id")
            return

        if not infovc_enabled.get(chat_id):
            return

        try:
            peer = await client.resolve_peer(chat_id)
            group_call = await client.send(GetGroupCall(peer=peer))
            call = group_call.call
            input_call = InputGroupCall(id=call.id, access_hash=call.access_hash)
            participants = await client.send(GetGroupParticipants(call=input_call, limit=100, offset=""))
        except Exception as e:
            LOGGER.warning(f"[VC DEBUG] Failed to fetch participants: {e}")
            return

        user_ids = {p.peer.user_id for p in participants.participants if hasattr(p.peer, "user_id")}
        old_users = vc_participants.get(chat_id, set())

        joined = user_ids - old_users
        left = old_users - user_ids

        vc_participants[chat_id] = user_ids

        for uid in joined:
            user = next((u for u in users if u.id == uid), None)
            if user:
                await app.send_message(
                    chat_id,
                    f"👤 **{user.first_name}** [`{uid}`] joined the voice chat.",
                )

        for uid in left:
            user = next((u for u in users if u.id == uid), None)
            if user:
                await app.send_message(
                    chat_id,
                    f"👤 **{user.first_name}** [`{uid}`] left the voice chat.",
                )

        LOGGER.debug(f"[VC DEBUG] Chat {chat_id}: {len(joined)} joined, {len(left)} left")

    elif isinstance(update, UpdateGroupCall):
        call = update.call
        call_id = call.id

        # Check if the call is active
        if hasattr(call, "duration") and call.duration == 0:
            # VC started
            for cid in await get_active_chats():
                try:
                    peer = await client.resolve_peer(cid)
                    group_call = await client.send(GetGroupCall(peer=peer))
                    if group_call.call.id == call_id:
                        call_to_chat[call_id] = cid
                        infovc_enabled[cid] = True
                        await add_active_video_chat(cid)
                        await app.send_message(cid, "📞 Voice chat started.")
                        LOGGER.info(f"[VC DEBUG] VC started in chat {cid}")
                        break
                except Exception:
                    continue
        else:
            # VC ended
            chat_id = call_to_chat.get(call_id)
            if chat_id:
                await remove_active_video_chat(chat_id)
                infovc_enabled[chat_id] = False
                await app.send_message(chat_id, "📴 Voice chat ended.")
                LOGGER.info(f"[VC DEBUG] VC ended in chat {chat_id}")
                call_to_chat.pop(call_id, None)
