import asyncio
from pyrogram import filters, raw
from pyrogram.types import Message
from pyrogram.raw.types import (
    UpdateGroupCallParticipants,
    UpdateGroupCall,
    UpdateGroupCallConnection,
)
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants
from Opus.core.call import Anony
from Opus import app
from Opus.utils.database import (
    get_active_video_chats,
    is_active_video_chat,
    add_active_video_chat,
    remove_active_video_chat,
)
from Opus import LOGGER

vc_participants = {}
infovc_enabled = {}


@app.on_message(filters.command(["infovc"]) & filters.group)
async def infovc_command(_, message: Message):
    if len(message.command) == 1:
        return await message.reply_text("Usage: `/infovc on` or `/infovc off`")
    
    arg = message.command[1].lower()
    chat_id = message.chat.id

    if arg == "on":
        infovc_enabled[chat_id] = True
        LOGGER(__name__).info(f"[INFOVC] Chat {chat_id} tracking set to True")
        await message.reply_text("🔊 VC tracking **enabled**.")
    elif arg == "off":
        infovc_enabled[chat_id] = False
        LOGGER(__name__).info(f"[INFOVC] Chat {chat_id} tracking set to False")
        await message.reply_text("🔇 VC tracking **disabled**.")
    else:
        await message.reply_text("❌ Invalid argument. Use `/infovc on` or `/infovc off`")


@Anony.userbot1.on_raw_update()
async def handle_groupcall_updates(client, update, users, chats):
    try:
        # Handle participant updates
        if isinstance(update, UpdateGroupCallParticipants):
            await handle_participants(client, update)
        
        # VC Started
        elif isinstance(update, UpdateGroupCall) and update.call:
            for chat_id in await get_active_video_chats():
                try:
                    gc = await client.send(GetGroupCall(peer=await client.resolve_peer(chat_id)))
                    if gc.call.id == update.call.id:
                        LOGGER(__name__).info(f"[VC STARTED] Matched group call started in {chat_id}")
                        await add_active_video_chat(chat_id)
                        await client.send_message(chat_id, "🚨 **Voice Chat Started**")
                        break
                except Exception as e:
                    LOGGER(__name__).error(f"[VC START ERROR] Chat {chat_id}: {e}")
                    continue

        # VC Ended
        elif isinstance(update, UpdateGroupCallConnection) and update.connection is None:
            for chat_id in await get_active_video_chats():
                try:
                    gc = await client.send(GetGroupCall(peer=await client.resolve_peer(chat_id)))
                    if gc.call is None:
                        await remove_active_video_chat(chat_id)
                        LOGGER(__name__).info(f"[VC ENDED] VC ended in {chat_id}")
                        await client.send_message(chat_id, "❌ **Voice Chat Ended**")
                        break
                except Exception as e:
                    continue

    except Exception as e:
        LOGGER(__name__).error(f"[RAW UPDATE ERROR] {e}")


async def handle_participants(client, update):
    chat_id = None
    try:
        active_chats = await get_active_video_chats()
        for active_chat in active_chats:
            try:
                gc = await client.send(GetGroupCall(peer=await client.resolve_peer(active_chat)))
                if gc.call.id == update.call.id:
                    chat_id = active_chat
                    break
            except Exception as e:
                continue

        if not chat_id:
            LOGGER(__name__).warning("[VC DEBUG] No active chat matched update.call.id")
            return

        if not infovc_enabled.get(chat_id, False):
            LOGGER(__name__).info(f"[VC DEBUG] Tracking disabled for {chat_id}")
            return

        response = await client.send(GetGroupParticipants(call=update.call, ids=[]))
        current = set(p.peer.user_id for p in response.participants)

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
                    f"✅ **{user.mention}** joined the VC.",
                )
            except Exception as e:
                LOGGER(__name__).error(f"[VC JOIN ERROR] {user_id} in {chat_id}: {e}")

        for user_id in left:
            try:
                user = await client.get_users(user_id)
                await client.send_message(
                    chat_id,
                    f"👋 **{user.mention}** left the VC.",
                )
            except Exception as e:
                LOGGER(__name__).error(f"[VC LEFT ERROR] {user_id} in {chat_id}: {e}")

    except Exception as e:
        LOGGER(__name__).error(f"[PARTICIPANT HANDLER ERROR] {e}")
