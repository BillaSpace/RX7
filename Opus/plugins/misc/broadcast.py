import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait

from Opus import app
from Opus.misc import SUDOERS
from Opus.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from Opus.utils.decorators.language import language
from Opus.utils.formatters import alpha_to_int
from config import adminlist

IS_BROADCASTING = False


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def broadcast_message(client, message, _):
    global IS_BROADCASTING
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1]
        if "-pin" in query:
            query = query.replace("-pin", "")
        if "-nobot" in query:
            query = query.replace("-nobot", "")
        if "-pinloud" in query:
            query = query.replace("-pinloud", "")
        if "-assistant" in query:
            query = query.replace("-assistant", "")
        if "-user" in query:
            query = query.replace("-user", "")
        if "-group" in query:
            query = query.replace("-group", "")
        if query.strip() == "":
            return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    sent = 0
    pin = 0
    failed = 0
    susr = 0
    failed_users = 0

    # Broadcast to groups
    if "-group" in message.text or ("-user" not in message.text and "-group" not in message.text):
        if "-nobot" not in message.text:
            chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
            for i in chats:
                try:
                    m = (
                        await app.forward_messages(i, y, x)
                        if message.reply_to_message
                        else await app.send_message(i, text=query)
                    )
                    if "-pin" in message.text:
                        try:
                            await m.pin(disable_notification=True)
                            pin += 1
                        except:
                            continue
                    elif "-pinloud" in message.text:
                        try:
                            await m.pin(disable_notification=False)
                            pin += 1
                        except:
                            continue
                    sent += 1
                    if sent % 20 == 0:
                        await asyncio.sleep(0.05)
                except FloodWait as fw:
                    flood_time = int(fw.value)
                    if flood_time > 200:
                        failed += 1
                        continue
                    await asyncio.sleep(flood_time)
                except:
                    failed += 1
                    continue
            try:
                await message.reply_text(_["broad_3"].format(sent, pin, failed))
            except:
                pass

    # Broadcast to users
    if "-user" in message.text or ("-user" not in message.text and "-group" not in message.text):
        users = [int(user["user_id"]) for user in await get_served_users()]
        for i in users:
            try:
                m = (
                    await app.forward_messages(i, y, x)
                    if message.reply_to_message
                    else await app.send_message(i, text=query)
                )
                susr += 1
                if susr % 20 == 0:
                    await asyncio.sleep(0.05)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    failed_users += 1
                    continue
                await asyncio.sleep(flood_time)
            except:
                failed_users += 1
                continue
        try:
            await message.reply_text(_["broad_4"].format(susr, failed_users))
        except:
            pass

    # Broadcast to assistant dialogs
    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from Opus.core.userbot import assistants

        for num in assistants:
            sent_assistant = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    await (
                        client.forward_messages(dialog.chat.id, y, x)
                        if message.reply_to_message
                        else client.send_message(dialog.chat.id, text=query)
                    )
                    sent_assistant += 1
                    if sent_assistant % 20 == 0:
                        await asyncio.sleep(0.03)
                except FloodWait as fw:
                    flood_time = int(fw.value)
                    if flood_time > 200:
                        continue
                    await asyncio.sleep(flood_time)
                except:
                    continue
            text += _["broad_7"].format(num, sent_assistant)
        try:
            await aw.edit_text(text)
        except:
            pass
    IS_BROADCASTING = False


async def auto_clean():
    while not await asyncio.sleep(5):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue


asyncio.create_task(auto_clean())
