import asyncio

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    ChatWriteForbidden,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Opus import YouTube, app
from Opus.misc import SUDOERS
from Opus.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from Opus.utils.inline import botplaylist_markup
from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string

links = {}


async def safe_reply(msg, text, markup=None, **kwargs):
    try:
        return await msg.reply_text(text, reply_markup=markup, **kwargs)
    except ChatWriteForbidden:
        pass
    except Exception:
        pass


async def safe_reply_photo(msg, photo, caption, buttons=None):
    try:
        return await msg.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
    except ChatWriteForbidden:
        pass
    except Exception:
        pass


def PlayWrapper(command):
    async def wrapper(client, message):
        language = await get_lang(message.chat.id)
        _ = get_string(language)

        # Anonymous check
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [[InlineKeyboardButton("ʜᴏᴡ ᴛᴏ ғɪx ?", callback_data="AnonymousAdmin")]]
            )
            return await safe_reply(message, _["general_3"], upl)

        # Maintenance check
        if await is_maintenance() is False:
            if message.from_user.id not in SUDOERS:
                return await safe_reply(
                    message,
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴜᴘᴅᴀᴛᴇs.",
                    disable_web_page_preview=True,
                )

        # Try delete user command
        try:
            await message.delete()
        except:
            pass

        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)

        if not (audio_telegram or video_telegram or url):
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await safe_reply(message, _["str_1"])
                buttons = botplaylist_markup(_)
                return await safe_reply_photo(message, PLAYLIST_IMG_URL, _["play_18"], buttons)

        # Channel Play
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if not chat_id:
                return await safe_reply(message, _["setting_7"])
            try:
                chat = await app.get_chat(chat_id)
                channel = chat.title
            except:
                return await safe_reply(message, _["cplay_4"])
        else:
            chat_id = message.chat.id
            channel = None

        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)

        # Admin Check
        if playty != "Everyone" and message.from_user.id not in SUDOERS:
            admins = adminlist.get(message.chat.id)
            if not admins:
                return await safe_reply(message, _["admin_13"])
            if message.from_user.id not in admins:
                return await safe_reply(message, _["play_4"])

        # Determine video/audio
        video = (
            True if message.command[0][0] == "v"
            else ("-v" in message.text or (len(message.command[0]) > 1 and message.command[0][1] == "v"))
        )
        fplay = True if message.command[0][-1] == "e" else None

        # Userbot join check
        if not await is_active_chat(chat_id):
            userbot = await get_assistant(chat_id)
            try:
                get = await app.get_chat_member(chat_id, userbot.id)
                if get.status in [ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]:
                    return await safe_reply(message, _["call_2"].format(
                        app.mention, userbot.id, userbot.name, userbot.username
                    ))
            except ChatAdminRequired:
                return await safe_reply(message, _["call_1"])
            except UserNotParticipant:
                invitelink = links.get(chat_id)
                if not invitelink:
                    if message.chat.username:
                        invitelink = f"https://t.me/{message.chat.username}"
                    else:
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await safe_reply(message, _["call_1"])
                        except Exception as e:
                            return await safe_reply(message, _["call_3"].format(app.mention, type(e).__name__))

                # Convert private join link
                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace("https://t.me/+", "https://t.me/joinchat/")

                try:
                    notify = await safe_reply(message, _["call_4"].format(app.mention))
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                        await asyncio.sleep(3)
                        await notify.edit(_["call_5"].format(app.mention))
                    except Exception as e:
                        return await safe_reply(message, _["call_3"].format(app.mention, type(e).__name__))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await safe_reply(message, _["call_3"].format(app.mention, type(e).__name__))

                links[chat_id] = invitelink

        return await command(
            client, message, _, chat_id, video, channel, playmode, url, fplay
        )

    return wrapper
