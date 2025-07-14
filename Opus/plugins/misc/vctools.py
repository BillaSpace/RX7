import asyncio
import logging

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message
from pyrogram.raw.types import InputGroupCall, UpdateGroupCall, UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants

from Opus import app, userbot, LOGGER 
from Opus.utils.database import (
    get_active_chats,
    is_active_chat,
    add_active_chat,
    remove_active_chat,
)
from Opus.utils.decorators.admins import ActualAdminCB

LOGGER = logging.getLogger(__name__)

infovc_enabled = set()
vc_participants = {}

@app.on_message(filters.command("vcstatus") & filters.group)
async def vc_status(_, message: Message):
    chat_id = message.chat.id
    if chat_id in infovc_enabled:
        infovc_enabled.remove(chat_id)
        await message.reply_text("🔴 VC participant tracking disabled.")
        LOGGER.info(f"[INFOVC] Chat {chat_id} tracking set to False")
    else:
        infovc_enabled.add(chat_id)
        await message.reply_text("🟢 VC participant tracking enabled.")
        LOGGER.info(f"[INFOVC] Chat {chat_id} tracking set to True")

@app.on_raw_update()
async def raw_listener(_, update, users, chats):
    if isinstance(update, UpdateGroupCallParticipants):
        await handle_participant_update(update)
    elif isinstance(update, UpdateGroupCall):
        await handle_call_status_update(update)

async def handle_participant_update(update: UpdateGroupCallParticipants):
    for chat_id in await get_active_chats():
        if chat_id not in infovc_enabled:
            continue
        try:
            client = userbot.one  # Only using first assistant
            full_call = await client.invoke(GetGroupCall(
                call=InputGroupCall(
                    id=update.call.id,
                    access_hash=update.call.access_hash
                )
            ))
            group_call_chat_id = full_call.call.chat_id if hasattr(full_call.call, "chat_id") else None
            if not group_call_chat_id or group_call_chat_id != chat_id:
                LOGGER.warning(f"[VC DEBUG] No active chat matched update.call.id: {update.call.id}")
                continue
            participants = await client.invoke(GetGroupParticipants(
                call=InputGroupCall(
                    id=update.call.id,
                    access_hash=update.call.access_hash
                ),
                limit=100,
                offset=""
            ))
            new_ids = set(p.peer.user_id for p in participants.participants if hasattr(p.peer, "user_id"))
            old_ids = vc_participants.get(chat_id, set())
            joined = new_ids - old_ids
            left = old_ids - new_ids
            vc_participants[chat_id] = new_ids
            if joined:
                for user_id in joined:
                    user = next((u for u in participants.users if u.id == user_id), None)
                    if user:
                        name = f"@{user.username}" if user.username else f"{user.first_name}"
                        await app.send_message(chat_id, f"➕ {name} joined the VC.")
            if left:
                for user_id in left:
                    name = "Someone"
                    await app.send_message(chat_id, f"➖ {name} left the VC.")
        except Exception as e:
            LOGGER.exception(f"[VC ERROR] {e}")

async def handle_call_status_update(update: UpdateGroupCall):
    for chat_id in await get_active_chats():
        if chat_id not in infovc_enabled:
            continue
        try:
            client = userbot.one
            full_call = await client.invoke(GetGroupCall(
                call=InputGroupCall(
                    id=update.call.id,
                    access_hash=update.call.access_hash
                )
            ))
            group_call_chat_id = full_call.call.chat_id if hasattr(full_call.call, "chat_id") else None
            if group_call_chat_id != chat_id:
                LOGGER.warning(f"[VC DEBUG] No active chat matched update.call.id: {update.call.id}")
                continue
            await app.send_message(chat_id, "🎙️ Voice chat has started.")
            vc_participants[chat_id] = set()
        except Exception as e:
            LOGGER.exception(f"[VC START ERROR] {e}")
