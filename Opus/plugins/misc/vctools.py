import asyncio
import logging
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.raw.types import (
    UpdateGroupCall,
    UpdateGroupCallParticipants,
    InputGroupCall
)
from pyrogram.raw.functions.phone import (
    GetGroupCall,
    GetGroupParticipants
)
from Opus import app, LOGGER
from Opus.core.call import group_assistant
from Opus.utils.database import (
    get_active_chats,
    is_active_chat,
    get_active_video_chats,
    is_active_video_chat,
)

infovc_enabled = {}
vc_participants = {}

# Toggle Command
@app.on_message(filters.command("infovc") & filters.group)
async def toggle_vc_debug(_, message: Message):
    chat_id = message.chat.id
    if not message.from_user:
        return

    if not message.from_user.id in (await app.get_chat_members(chat_id)):
        return await message.reply("❌ You must be in this group to use this.")

    current = infovc_enabled.get(chat_id, False)
    infovc_enabled[chat_id] = not current
    status = "enabled" if not current else "disabled"
    LOGGER.info(f"[INFOVC] Chat {chat_id} tracking set to {not current}")
    await message.reply(f"📢 VC participant tracking `{status}` in this chat.")

# Participant Updates Handler
async def handle_participant_update(update: UpdateGroupCallParticipants):
    call = update.call
    call_id = call.id
    access_hash = call.access_hash

    try:
        for chat_id in infovc_enabled:
            if not await is_active_chat(chat_id):
                continue

            assistant = await group_assistant(None, chat_id)
            input_call = InputGroupCall(id=call_id, access_hash=access_hash)
            group_call = await assistant.invoke(GetGroupParticipants(
                call=input_call,
                limit=0,
                offset=""
            ))

            new_sources = {p.source: p.user_id for p in group_call.participants}
            old_sources = vc_participants.get(chat_id, {})

            joined = [uid for src, uid in new_sources.items() if src not in old_sources]
            left = [uid for src, uid in old_sources.items() if src not in new_sources]

            vc_participants[chat_id] = new_sources

            for user_id in joined:
                user = await assistant.get_users(user_id)
                await app.send_message(chat_id, f"✅ **{user.first_name}** joined the VC.")

            for user_id in left:
                user = await assistant.get_users(user_id)
                await app.send_message(chat_id, f"❌ **{user.first_name}** left the VC.")

    except Exception as e:
        LOGGER.warning(f"[VC DEBUG] Error in handle_participant_update: {e}")

# VC Start/End Handler
async def handle_call_status_update(update: UpdateGroupCall):
    call = update.call
    call_id = call.id
    access_hash = call.access_hash

    try:
        for chat_id in infovc_enabled:
            if not await is_active_chat(chat_id):
                continue

            assistant = await group_assistant(None, chat_id)
            input_call = InputGroupCall(id=call_id, access_hash=access_hash)

            try:
                details = await assistant.invoke(GetGroupCall(call=input_call))
                await app.send_message(chat_id, "🔴 **Voice Chat Started!**")
            except Exception:
                await app.send_message(chat_id, "⚪️ **Voice Chat Ended!**")

    except Exception as e:
        LOGGER.warning(f"[VC DEBUG] Error in handle_call_status_update: {e}")

# Raw Listener with concurrency
@app.on_raw_update()
async def raw_listener(_, update, users, chats):
    try:
        if isinstance(update, UpdateGroupCallParticipants):
            asyncio.create_task(handle_participant_update(update))
        elif isinstance(update, UpdateGroupCall):
            asyncio.create_task(handle_call_status_update(update))
    except Exception as e:
        LOGGER.exception(f"[RAW_UPDATE ERROR] {e}")
