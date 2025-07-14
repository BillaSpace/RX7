from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.raw import functions, types
from typing import Union, List
import asyncio
from datetime import datetime

from Opus import app

# Voice Chat Tracking System
class VCTracker:
    def __init__(self):
        self.infovc_enabled = True
        self.active_calls = {}  # {chat_id: {"call": GroupCall, "participants": {user_id: join_time}}}
        self.update_interval = 1  # seconds between updates

    async def start(self):
        """Start the background update task"""
        asyncio.create_task(self._update_participants_loop())

    async def _update_participants_loop(self):
        """Background task to regularly update participant list"""
        while True:
            try:
                if self.infovc_enabled:
                    await self._update_all_active_calls()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in update loop: {e}")
                await asyncio.sleep(1)

    async def _update_all_active_calls(self):
        """Update participant lists for all active calls"""
        for chat_id in list(self.active_calls.keys()):
            try:
                await self._update_call_participants(chat_id)
            except Exception as e:
                print(f"Error updating call for chat {chat_id}: {e}")

    async def _update_call_participants(self, chat_id: int):
        """Get current participants using raw API"""
        if chat_id not in self.active_calls:
            return

        call = self.active_calls[chat_id]["call"]
        try:
            participants = await app.send(
                functions.phone.GetGroupParticipants(
                    call=types.InputGroupCall(
                        id=call.id,
                        access_hash=call.access_hash
                    ),
                    ids=[],
                    sources=[],
                    offset="",
                    limit=100
                )
            )

            current_participants = set()
            for participant in participants.participants:
                user_id = participant.peer.user_id
                current_participants.add(user_id)
                
                # Add new participants
                if user_id not in self.active_calls[chat_id]["participants"]:
                    self.active_calls[chat_id]["participants"][user_id] = datetime.now()
                    await self._notify_join(chat_id, user_id)

            # Remove left participants
            for user_id in list(self.active_calls[chat_id]["participants"].keys()):
                if user_id not in current_participants:
                    join_time = self.active_calls[chat_id]["participants"].pop(user_id)
                    await self._notify_leave(chat_id, user_id, join_time)

        except Exception as e:
            print(f"Error getting participants for chat {chat_id}: {e}")

    async def _notify_join(self, chat_id: int, user_id: int):
        """Notify when a user joins"""
        try:
            user = await app.get_users(user_id)
            text = (
                f"#JoinVoiceChat\n"
                f"Name: {user.mention}\n"
                f"ID: {user.id}\n"
                f"Action: Joined voice chat"
            )
            await app.send_message(chat_id, text)
        except Exception as e:
            print(f"Error notifying join: {e}")

    async def _notify_leave(self, chat_id: int, user_id: int, join_time: datetime):
        """Notify when a user leaves"""
        try:
            user = await app.get_users(user_id)
            duration = datetime.now() - join_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            text = (
                f"#LeaveVoiceChat\n"
                f"Name: {user.mention}\n"
                f"ID: {user.id}\n"
                f"Action: Left voice chat\n"
                f"Duration: {hours}h {minutes}m {seconds}s"
            )
            await app.send_message(chat_id, text)
        except Exception as e:
            print(f"Error notifying leave: {e}")

# Initialize tracker
vc_tracker = VCTracker()
asyncio.create_task(vc_tracker.start())

# Command decorator
def command(commands: Union[str, List[str]]):
    return filters.command(commands, prefixes=["/"])

# Command to toggle /infovc on/off
@app.on_message(command(["infovc"]))
async def toggle_infovc(_, message: Message):
    if len(message.command) > 1:
        state = message.command[1].lower()
        if state == "on":
            vc_tracker.infovc_enabled = True
            await message.reply("Voice chat participant tracking is now enabled.")
        elif state == "off":
            vc_tracker.infovc_enabled = False
            await message.reply("Voice chat participant tracking is now disabled.")
        else:
            await message.reply("Usage: /infovc on or /infovc off")
    else:
        await message.reply("Usage: /infovc on or /infovc off")

# Command to show current VC participants
@app.on_message(command(["vclist", "vcusers"]))
async def show_vc_participants(_, message: Message):
    if not vc_tracker.infovc_enabled:
        await message.reply("Voice chat tracking is currently disabled. Enable with /infovc on")
        return

    chat_id = message.chat.id
    if chat_id not in vc_tracker.active_calls or not vc_tracker.active_calls[chat_id]["participants"]:
        await message.reply("No active voice chat or participants.")
        return

    participants = vc_tracker.active_calls[chat_id]["participants"]
    text = "**Current Voice Chat Participants:**\n\n"
    
    for user_id, join_time in participants.items():
        try:
            user = await app.get_users(user_id)
            duration = datetime.now() - join_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            text += f"• {user.mention} - {hours}h {minutes}m {seconds}s\n"
        except Exception as e:
            print(f"Error getting user info: {e}")
            text += f"• Unknown user (ID: {user_id})\n"

    await message.reply(text)

# Handler to detect new voice chats
@app.on_message(filters.video_chat_started)
async def voice_chat_started(_, message: Message):
    chat_id = message.chat.id
    try:
        # Get call info using raw API
        call = await app.send(
            functions.phone.GetGroupCall(
                call=types.InputGroupCall(
                    id=message.voice_chat.id,
                    access_hash=0  # You'll need to get the actual access hash
                ),
                limit=100
            )
        )
        
        vc_tracker.active_calls[chat_id] = {
            "call": call.call,
            "participants": {}
        }
        await message.reply("Voice chat started. Tracking participants...")
    except Exception as e:
        print(f"Error tracking new voice chat: {e}")

# Handler to detect ended voice chats
@app.on_message(filters.video_chat_ended)
async def voice_chat_ended(_, message: Message):
    chat_id = message.chat.id
    if chat_id in vc_tracker.active_calls:
        vc_tracker.active_calls.pop(chat_id)
    await message.reply("Voice chat ended. Stopped tracking participants.")
