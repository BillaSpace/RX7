from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls.types import Update, GroupCallParticipant, GroupCallEnded
from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall
from typing import Union, List
import asyncio

from AnonXMusic import app  # Main Pyrogram client
from call import Anony  # Call class instance from call.py
from Opus import LOGGER
from Opus.utils.database import group_assistant, add_active_chat, remove_active_chat

# Store notification state and monitoring status per chat
infovc_enabled = {}  # {chat_id: bool}
monitoring_tasks = {}  # {chat_id: bool}

# Command decorator
def command(commands: Union[str, List[str]]):
    return filters.command(commands, prefixes=["/"])

# Command to toggle /infovc on/off
@app.on_message(command(["infovc"]))
async def toggle_infovc(client: Client, message: Message):
    chat_id = message.chat.id
    if len(message.command) > 1:
        state = message.command[1].lower()
        if state == "on":
            infovc_enabled[chat_id] = True
            if chat_id not in monitoring_tasks:
                try:
                    assistant = await group_assistant(Anony, chat_id)
                    # Join voice chat with a silent stream
                    await assistant.join_group_call(chat_id, MediaStream("silence.mp3"))
                    monitoring_tasks[chat_id] = True
                    await add_active_chat(chat_id)  # Sync with your database
                    await message.reply("Voice chat join/leave notifications are now enabled.")
                except NoActiveGroupCall:
                    infovc_enabled[chat_id] = False
                    await message.reply("No active voice chat in this group.")
                except AlreadyJoinedError:
                    monitoring_tasks[chat_id] = True
                    await message.reply("Voice chat join/leave notifications are now enabled.")
                except Exception as e:
                    infovc_enabled[chat_id] = False
                    await message.reply(f"Error enabling infovc: {e}")
                    LOGGER(__name__).error(f"Error enabling infovc for chat {chat_id}: {e}")
        elif state == "off":
            infovc_enabled[chat_id] = False
            if chat_id in monitoring_tasks:
                try:
                    assistant = await group_assistant(Anony, chat_id)
                    await assistant.leave_group_call(chat_id)
                    del monitoring_tasks[chat_id]
                    await remove_active_chat(chat_id)  # Sync with your database
                    await message.reply("Voice chat join/leave notifications are now disabled.")
                except Exception as e:
                    await message.reply(f"Error disabling infovc: {e}")
                    LOGGER(__name__).error(f"Error disabling infovc for chat {chat_id}: {e}")
        else:
            await message.reply("Usage: /infovc on or /infovc off")
    else:
        await message.reply("Usage: /infovc on or /infovc off")

# Command to list current voice chat participants
@app.on_message(command(["listvc"]))
async def list_vc_participants(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id not in infovc_enabled or not infovc_enabled[chat_id]:
        await message.reply("Voice chat monitoring is not enabled. Use /infovc on to enable.")
        return

    try:
        assistant = await group_assistant(Anony, chat_id)
        participants = await assistant.get_participants(chat_id)
        if not participants:
            await message.reply("No participants in the voice chat.")
            return
        participant_names = []
        for p in participants:
            try:
                user = await app.get_users(p.user_id)
                participant_names.append(f"{user.mention} ({user.id})")
            except Exception:
                participant_names.append(f"Unknown User ({p.user_id})")
        await message.reply(
            f"Current Voice Chat Participants:\n" + "\n".join(participant_names)
        )
    except NoActiveGroupCall:
        infovc_enabled[chat_id] = False
        if chat_id in monitoring_tasks:
            del monitoring_tasks[chat_id]
        await remove_active_chat(chat_id)  # Sync with your database
        await message.reply("No active voice chat in this group.")
    except Exception as e:
        await message.reply(f"Error listing participants: {e}")
        LOGGER(__name__).error(f"Error listing participants for chat {chat_id}: {e}")

# PyTgCalls event handler for participant updates
async def handle_participant_update(pytgcalls: PyTgCalls, update: Update):
    if isinstance(update, GroupCallParticipant):
        chat_id = update.chat_id
        if chat_id not in infovc_enabled or not infovc_enabled[chat_id]:
            return

        try:
            user = await app.get_users(update.participant.user_id)
            if update.participant.is_joined:
                text = (
                    f"#JoinVoiceChat\n"
                    f"Name: {user.mention}\n"
                    f"ID: {user.id}\n"
                    f"Action: Joined the voice chat"
                )
            else:
                text = (
                    f"#LeaveVoiceChat\n"
                    f"Name: {user.mention}\n"
                    f"ID: {user.id}\n"
                    f"Action: Left the voice chat"
                )
            await app.send_message(chat_id, text)
        except Exception as e:
            LOGGER(__name__).error(f"Error handling participant update for chat {chat_id}: {e}")

# PyTgCalls event handler for voice chat end
async def handle_group_call_ended(pytgcalls: PyTgCalls, update: Update):
    if isinstance(update, GroupCallEnded):
        chat_id = update.chat_id
        if chat_id in infovc_enabled:
            infovc_enabled[chat_id] = False
            if chat_id in monitoring_tasks:
                del monitoring_tasks[chat_id]
            try:
                await remove_active_chat(chat_id)  # Sync with your database
                await app.send_message(chat_id, "Voice chat has ended. Notifications disabled.")
            except Exception as e:
                LOGGER(__name__).error(f"Error sending voice chat end message for chat {chat_id}: {e}")

# PyTgCalls event handler for voice chat creation
async def handle_group_call_created(pytgcalls: PyTgCalls, update: Update):
    if isinstance(update, pytgcalls.types.GroupCallCreated):
        chat_id = update.chat_id
        if chat_id in infovc_enabled and infovc_enabled[chat_id] and chat_id not in monitoring_tasks:
            try:
                assistant = await group_assistant(Anony, chat_id)
                await assistant.join_group_call(chat_id, MediaStream("silence.mp3"))
                monitoring_tasks[chat_id] = True
                await add_active_chat(chat_id)  # Sync with your database
            except AlreadyJoinedError:
                monitoring_tasks[chat_id] = True
            except NoActiveGroupCall:
                LOGGER(__name__).info(f"No active group call in chat {chat_id}")
            except Exception as e:
                LOGGER(__name__).error(f"Error joining voice chat for chat {chat_id}: {e}")

# Register PyTgCalls event handlers for all assistants
for pytgcalls in [Anony.one, Anony.two, Anony.three, Anony.four, Anony.five]:
    if pytgcalls:
        pytgcalls.on_update()(handle_participant_update)
        pytgcalls.on_group_call_ended()(handle_group_call_ended)
        pytgcalls.on_group_call_created()(handle_group_call_created)
