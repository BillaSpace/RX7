import asyncio
import logging

from pyrogram import filters, raw
from pyrogram.types import Message
from pyrogram.raw.types import (
    UpdateGroupCallParticipants,
    UpdateGroupCall,
    UpdateGroupCallDeleted,
)
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants

from Opus import app
from Opus.core.call import Anony
from Opus.utils.database import (
    get_active_video_chats,
    is_active_video_chat,
)
from Opus import LOGGER 

LOG = logging.getLogger("Opus.plugins.misc.vctools")

# Track VC participant states
vc_participants = {}

# Enable tracking for chats
infovc_enabled = {}


@app.on_message(filters.command("infovc") & filters.group)
async def enable_vc_tracking(_, message: Message):
    chat_id = message.chat.id
    infovc_enabled[chat_id] = True
    LOG.info(f"[INFOVC] Chat {chat_id} tracking set to True")
    await message.reply_text("✅ Voice Chat tracking enabled in this group.")


@Anony.userbot1.on_raw_update()
async def handle_vc_updates(client, update, users, chats):
    try:
        if isinstance(update, UpdateGroupCallParticipants):
            await handle_participant_change(client, update)
        elif isinstance(update, UpdateGroupCall):
            await handle_groupcall_started(client, update)
        elif isinstance(update, UpdateGroupCallDeleted):
            await handle_groupcall_ended(client, update)
    except Exception as e:
        LOG.exception(f"[RAW UPDATE ERROR] {e}")


async def resolve_chat_id_from_call(client, call_obj):
    active_vcs = await get_active_video_chats()
    for chat_id in active_vcs:
        try:
            resolved = await client.resolve_peer(chat_id)
            call_info = await client.send(GetGroupCall(peer=resolved))
            if call_info.call.id == call_obj.id:
                LOG.debug(f"[VC DEBUG] Matched call.id to chat {chat_id}")
                return chat_id
        except Exception as e:
            LOG.warning(f"[VC DEBUG] Error checking chat {chat_id}: {e}")
    LOG.warning("[VC DEBUG] No active chat matched update.call.id")
    return None


async def handle_participant_change(client, update: UpdateGroupCallParticipants):
    chat_id = await resolve_chat_id_from_call(client, update.call)
    if not chat_id:
        return
    if not infovc_enabled.get(chat_id, False):
        LOG.debug(f"[VC DEBUG] Tracking disabled for chat {chat_id}")
        return
    try:
        resp = await client.send(GetGroupParticipants(call=update.call, ids=[]))
        current = set(p.peer.user_id for p in resp.participants)
    except Exception as e:
        LOG.warning(f"[VC DEBUG] Failed fetching participants: {e}")
        return

    old = vc_participants.get(chat_id, set())
    joined = current - old
    left = old - current
    vc_participants[chat_id] = current

    LOG.info(f"[VC DEBUG] Chat {chat_id}: {len(joined)} joined, {len(left)} left")

    for user_id in joined:
        try:
            user = await client.get_users(user_id)
            await client.send_message(
                chat_id,
                f"🎙️ **User Joined VC**\n**Name:** {user.mention}",
            )
        except Exception as e:
            LOG.warning(f"[VC JOIN ERROR] {user_id} in {chat_id}: {e}")

    for user_id in left:
        try:
            user = await client.get_users(user_id)
            await client.send_message(
                chat_id,
                f"📤 **User Left VC**\n**Name:** {user.mention}",
            )
        except Exception as e:
            LOG.warning(f"[VC LEFT ERROR] {user_id} in {chat_id}: {e}")


async def handle_groupcall_started(client, update: UpdateGroupCall):
    chat_id = await resolve_chat_id_from_call(client, update.call)
    if not chat_id:
        return
    if not infovc_enabled.get(chat_id, False):
        LOG.debug(f"[VC DEBUG] VC started but tracking disabled for chat {chat_id}")
        return
    LOG.info(f"[VC STARTED] VC started in chat {chat_id}")
    try:
        await client.send_message(
            chat_id,
            "🔊 **Voice Chat Started**\n\nVoice chat has been started in this group.",
        )
    except Exception as e:
        LOG.warning(f"[VC STARTED ERROR] {chat_id}: {e}")


async def handle_groupcall_ended(client, update: UpdateGroupCallDeleted):
    chat_id = await resolve_chat_id_from_call(client, update.call)
    if not chat_id:
        return
    if not infovc_enabled.get(chat_id, False):
        LOG.debug(f"[VC DEBUG] VC ended but tracking disabled for chat {chat_id}")
        return
    vc_participants.pop(chat_id, None)
    LOG.info(f"[VC ENDED] VC ended in chat {chat_id}")
    try:
        await client.send_message(
            chat_id,
            "📴 **Voice Chat Ended**\n\nVoice chat has ended in this group.",
        )
    except Exception as e:
        LOG.warning(f"[VC ENDED ERROR] {chat_id}: {e}")
