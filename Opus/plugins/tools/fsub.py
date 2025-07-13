from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient
from Opus import app
import asyncio
from Opus.misc import SUDOERS
from config import MONGO_DB_URI
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
    ChannelInvalid,
)

fsubdb = MongoClient(MONGO_DB_URI)
forcesub_collection = fsubdb.status_db.status

@app.on_message(filters.command(["fsub", "forcesub"]) & filters.group)
async def set_forcesub(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Check if user is group owner or sudoer
    member = await client.get_chat_member(chat_id, user_id)
    if not (member.status == "creator" or user_id in SUDOERS):
        return await message.reply_text("Only group owners or sudoers can use this command.")

    # Handle disable command
    if len(message.command) == 2 and message.command[1].lower() in ["off", "disable"]:
        forcesub_collection.delete_one({"chat_id": chat_id})
        return await message.reply_text("Force subscription has been disabled for this group.")

    # Validate command usage
    if len(message.command) != 2:
        return await message.reply_text("Usage: /fsub <channel username or ID> or /fsub off to disable")

    channel_input = message.command[1]

    try:
        # Get channel information
        channel_info = await client.get_chat(channel_input)
        channel_id = channel_info.id
        channel_title = channel_info.title
        channel_link = await app.export_chat_invite_link(channel_id)
        channel_username = f"{channel_info.username}" if channel_info.username else channel_link
        channel_members_count = channel_info.members_count

        # Check if bot is a member of the channel
        bot_id = (await client.get_me()).id
        try:
            bot_member = await app.get_chat_member(channel_id, bot_id)
            if not bot_member:
                return await message.reply_text("I am not a member of the channel. Please add me first.")
        except ChannelInvalid:
            return await message.reply_text("Invalid channel. Please provide a valid channel ID or username.")

        # Check if bot is an admin
        bot_is_admin = False
        async for admin in app.get_chat_members(channel_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if admin.user.id == bot_id:
                bot_is_admin = True
                break

        if not bot_is_admin:
            return await message.reply_text(
                "I'm not an admin in this channel.\n\n"
                "Please make me an admin with:\n\n"
                "Invite New Members\n\n"
                "Then use /fsub <channel username> to set force subscription.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Add me in channel", url=f"https://t.me/{app.username}?startchannel=s&admin=invite_users+manage_video_chats")]]
                )
            )

        # Update database
        forcesub_collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"channel_id": channel_id, "channel_username": channel_username}},
            upsert=True
        )

        set_by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

        await message.reply_text(
            f"Force subscription set to {channel_title} for this group.\n\n"
            f"Channel ID: {channel_id}\n"
            f"Channel: {channel_username}\n"
            f"Member count: {channel_members_count}\n"
            f"Set by: {set_by_user}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Close", callback_data="close_force_sub")]]
            )
        )

    except ChannelInvalid:
        return await message.reply_text("Invalid channel ID or username. Please provide a valid channel.")
    except Exception as e:
        return await message.reply_text(
            f"Error accessing channel: {str(e)}\n\n"
            "Please ensure the channel exists and I have access to it.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Add me in channel", url=f"https://t.me/{app.username}?startchannel=s&admin=invite_users+manage_video_chats")]]
            )
        )

@app.on_message(filters.command(["rmfsub"]) & filters.group)
async def remove_forcesub(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Check if user is group owner or sudoer
    member = await client.get_chat_member(chat_id, user_id)
    if not (member.status == "creator" or user_id in SUDOERS):
        return await message.reply_text("Only group owners or sudoers can use this command.")

    # Handle command arguments
    if len(message.command) > 2:
        return await message.reply_text("Usage: /rmfsub [all] or /rmfsub (removes force subscription for this group)")

    if len(message.command) == 2 and message.command[1].lower() == "all":
        # Only sudoers can remove all entries
        if user_id not in SUDOERS:
            return await message.reply_text("Only sudoers can remove all force subscription entries.")
        try:
            result = forcesub_collection.delete_many({})
            return await message.reply_text(f"Removed {result.deleted_count} force subscription entries from the database.")
        except Exception as e:
            return await message.reply_text(f"Error removing all force subscriptions: {str(e)}")

    # Remove force subscription for the current group
    try:
        result = forcesub_collection.delete_one({"chat_id": chat_id})
        if result.deleted_count > 0:
            return await message.reply_text("Force subscription has been removed for this group.")
        else:
            return await message.reply_text("No force subscription entry found for this group.")
    except Exception as e:
        return await message.reply_text(f"Error removing force subscription: {str(e)}")

@app.on_callback_query(filters.regex("close_force_sub"))
async def close_force_sub(client: Client, callback_query: CallbackQuery):
    await callback_query.answer("Closed")
    await callback_query.message.delete()

async def check_forcesub(client: Client, message: Message):
    chat_id = message.chat.id
    if not message.from_user:
        return
    user_id = message.from_user.id

    forcesub_data = forcesub_collection.find_one({"chat_id": chat_id})
    if not forcesub_data:
        return

    channel_id = forcesub_data["channel_id"]
    channel_username = forcesub_data["channel_username"]

    try:
        user_member = await app.get_chat_member(channel_id, user_id)
        if user_member:
            return
    except UserNotParticipant:
        await message.delete()
        if channel_username:
            channel_url = f"https://t.me/{channel_username}"
        else:
            try:
                invite_link = await app.export_chat_invite_link(channel_id)
                channel_url = invite_link
            except ChannelInvalid:
                forcesub_collection.delete_one({"chat_id": chat_id})
                return await message.reply_text("Force subscription channel is invalid. Force subscription has been disabled.")
        await message.reply_text(
            f"<blockquote><b>👋 Hello {message.from_user.mention},\n\nYou need to join to send messages in this group.</b></blockquote>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join", url=channel_url)]]
            )
        )
    except ChatAdminRequired:
        forcesub_collection.delete_one({"chat_id": chat_id})
        return await message.reply_text("I'm no longer an admin in the force subscription channel. Force subscription has been disabled.")
    except ChannelInvalid:
        forcesub_collection.delete_one({"chat_id": chat_id})
        return await message.reply_text("The force subscription channel is invalid. Force subscription has been disabled.")
    except Exception as e:
        return await message.reply_text(f"Error checking channel membership: {str(e)}")

@app.on_message(filters.group, group=30)
async def enforce_forcesub(client: Client, message: Message):
    result = await check_forcesub(client, message)
    if result is None:
        return
