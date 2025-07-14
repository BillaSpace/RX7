import asyncio
import logging

from pyrogram import filters
from pyrogram.raw.types import UpdateGroupCall, UpdateGroupCallParticipants
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from pyrogram.raw.types import InputGroupCall

from Opus import app, LOGGER
from Opus.core.call import group_assistant
from Opus.utils.database import get_lang, get_active_chats, is_active_chat
from Opus.utils.database import add_active_chat, remove_active_chat, add_active_video_chat, is_active_video_chat
from strings import get_string

infovc_enabled_chats = set()
vc_participants = {}

LOG = LOGGER(__name__)

@app.on_message(filters.command("infovc") & filters.group)
async def toggle_infovc(client, message):
    chat_id = message.chat.id
    language = await get_lang(chat_id)
    _ = get_string(language)

    if chat_id in infovc_enabled_chats:
        infovc_enabled_chats.remove(chat_id)
        LOG.info(f"[INFOVC] Chat {chat_id} tracking set to False")
        return await message.reply_text("❌ Voice Chat tracking disabled.")
    else:
        infovc_enabled_chats.add(chat_id)
        LOG.info(f"[INFOVC] Chat {chat_id} tracking set to True")
        return await message.reply_text("✅ Voice Chat tracking enabled.")

@app.on_raw_update()
async def raw_vc_monitor(client, update, users, chats):
    try:
        if isinstance(update, UpdateGroupCall):
            LOG.debug("[VC DEBUG] Detected UpdateGroupCall.")
            await handle_group_call_update(client, update)

        elif isinstance(update, UpdateGroupCallParticipants):
            LOG.debug("[VC DEBUG] Detected UpdateGroupCallParticipants.")
            await handle_group_call_participants(client, update)

    except Exception as e:
        LOG.error(f"[VC ERROR] {e}")

async def handle_group_call_update(client, update):
    try:
        group_call = update.call
        chat_id = await get_chat_id_from_group_call(client, group_call)

        if chat_id and chat_id in infovc_enabled_chats:
            if update.call:
                LOG.info(f"[VC] Group Call updated in {chat_id}")
                await app.send_message(chat_id, "🎙️ Voice Chat has been started or updated.")
        else:
            LOG.warning("[VC DEBUG] No active chat matched update.call.id (GroupCall update)")

    except Exception as e:
        LOG.error(f"[VC ERROR] handle_group_call_update: {e}")

async def handle_group_call_participants(client, update):
    try:
        group_call = update.call
        participants = update.participants

        chat_id = await get_chat_id_from_group_call(client, group_call)
        if chat_id is None:
            LOG.warning("[VC DEBUG] No active chat matched update.call.id (Participants update)")
            return

        if chat_id not in infovc_enabled_chats:
            return

        assistant = await group_assistant(client, chat_id)

        call = InputGroupCall(id=group_call.id, access_hash=group_call.access_hash)
        call_info = await assistant.invoke(GetGroupParticipants(call=call, offset="", limit=0))

        current_participants = [p.user_id for p in call_info.participants]
        previous_participants = vc_participants.get(chat_id, set())

        joined = set(current_participants) - previous_participants
        left = previous_participants - set(current_participants)

        vc_participants[chat_id] = set(current_participants)

        if joined:
            for user_id in joined:
                user = next((u for u in call_info.users if u.id == user_id), None)
                if user:
                    name = f"{user.first_name} {user.last_name or ''}".strip()
                    await app.send_message(chat_id, f"➕ {name} joined the VC.")

        if left:
            for user_id in left:
                # Use cached name if possible
                name = "A user"
                await app.send_message(chat_id, f"➖ {name} left the VC.")

    except Exception as e:
        LOG.error(f"[VC ERROR] handle_group_call_participants: {e}")

async def get_chat_id_from_group_call(client, group_call):
    try:
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            assistant = await group_assistant(client, chat_id)
            try:
                call_info = await assistant.invoke(GetGroupCall(peer=await app.resolve_peer(chat_id)))
                if call_info.call.id == group_call.id:
                    return chat_id
            except Exception as e:
                continue
        return None
    except Exception as e:
        LOG.error(f"[VC ERROR] get_chat_id_from_group_call: {e}")
        return None
