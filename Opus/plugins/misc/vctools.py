from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.raw import functions, types
from datetime import datetime
import asyncio
from typing import Dict, Set, Union, List
from Opus import app

class VCTracker:
    def __init__(self):
        self.active_calls: Dict[int, Dict[int, datetime]] = {}
        self.update_interval = 20
        self.running = False
        self.tracking_enabled = True

    async def start(self):
        if not self.running:
            self.running = True
            asyncio.create_task(self._tracker_loop())

    async def _tracker_loop(self):
        while self.running:
            try:
                await self._update_all_calls()
            except Exception as e:
                print(f"Tracker error: {e}")
            await asyncio.sleep(self.update_interval)

    async def _update_all_calls(self):
        for chat_id in list(self.active_calls.keys()):
            try:
                await self._update_call_participants(chat_id)
            except Exception as e:
                print(f"Error updating call {chat_id}: {e}")

    async def _update_call_participants(self, chat_id: int):
        try:
            call = await self._get_group_call(chat_id)
            if not call:
                if chat_id in self.active_calls:
                    del self.active_calls[chat_id]
                return

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

            current_participants = {p.peer.user_id for p in participants.participants}
            await self._process_participant_changes(chat_id, current_participants)

        except Exception as e:
            print(f"Error getting participants for chat {chat_id}: {e}")

    async def _get_group_call(self, chat_id: int):
        try:
            full_chat = await app.send(
                functions.messages.GetFullChat(chat_id=chat_id)
            )
            if hasattr(full_chat.full_chat, 'call'):
                return full_chat.full_chat.call
            return None
        except Exception as e:
            print(f"Error getting call for chat {chat_id}: {e}")
            return None

    async def _process_participant_changes(self, chat_id: int, current_participants: Set[int]):
        if chat_id not in self.active_calls:
            self.active_calls[chat_id] = {}

        for user_id in current_participants:
            if user_id not in self.active_calls[chat_id]:
                self.active_calls[chat_id][user_id] = datetime.now()
                await self._notify_join(chat_id, user_id)

        for user_id in list(self.active_calls[chat_id].keys()):
            if user_id not in current_participants:
                join_time = self.active_calls[chat_id].pop(user_id)
                await self._notify_leave(chat_id, user_id, join_time)

    async def _notify_join(self, chat_id: int, user_id: int):
        if not self.tracking_enabled:
            return
        try:
            user = await app.get_users(user_id)
            await app.send_message(
                chat_id,
                f"🎤 {user.mention} joined voice chat"
            )
        except Exception as e:
            print(f"Error notifying join: {e}")

    async def _notify_leave(self, chat_id: int, user_id: int, join_time: datetime):
        if not self.tracking_enabled:
            return
        try:
            user = await app.get_users(user_id)
            duration = datetime.now() - join_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            await app.send_message(
                chat_id,
                f"🚪 {user.mention} left after {hours}h {minutes}m {seconds}s"
            )
        except Exception as e:
            print(f"Error notifying leave: {e}")

    async def get_participants_text(self, chat_id: int) -> str:
        participants = self.active_calls.get(chat_id, {})
        if not participants:
            return "No active participants in voice chat."
        
        text = "**🎤 Current Participants:**\n\n"
        for user_id, join_time in participants.items():
            try:
                user = await app.get_users(user_id)
                duration = datetime.now() - join_time
                hours, remainder = divmod(duration.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                text += f"• {user.mention} - {hours}h {minutes}m {seconds}s\n"
            except:
                text += f"• Unknown User (ID: {user_id})\n"
        return text

tracker = VCTracker()

def command(cmd: Union[str, List[str]]):
    return filters.command(cmd, prefixes=["/", "!"])

@app.on_message(command(["infovc", "vcmode"]))
async def toggle_tracking(_, message: Message):
    if len(message.command) > 1:
        arg = message.command[1].lower()
        if arg == "on":
            tracker.tracking_enabled = True
            await message.reply("✅ Voice chat tracking enabled")
        elif arg == "off":
            tracker.tracking_enabled = False
            await message.reply("❌ Voice chat tracking disabled")
        else:
            await message.reply("Usage: /infovc [on|off]")
    else:
        status = "enabled" if tracker.tracking_enabled else "disabled"
        await message.reply(f"Tracking is {status}\nUsage: /vctrack [on|off]")

@app.on_message(command(["vclist", "vcusers"]))
async def show_participants(_, message: Message):
    text = await tracker.get_participants_text(message.chat.id)
    await message.reply(text)

@app.on_message(command(["vcinfo", "vcstatus"]))
async def voice_chat_info(_, message: Message):
    chat_id = message.chat.id
    try:
        full_chat = await app.send(
            functions.messages.GetFullChat(chat_id=chat_id)
        )
        
        if hasattr(full_chat.full_chat, 'call'):
            call = full_chat.full_chat.call
            participants_count = len(tracker.active_calls.get(chat_id, {}))
            
            text = (
                "**📊 Voice Chat Info**\n\n"
                f"• Participants: {participants_count}\n"
                f"• Tracking: {'✅ Enabled' if tracker.tracking_enabled else '❌ Disabled'}"
            )
        else:
            text = "No active voice chat"
    except Exception as e:
        text = f"Error: {str(e)}"
    
    await message.reply(text)

@app.on_message(filters.video_chat_started)
async def voice_chat_started(_, message: Message):
    await tracker.start()

@app.on_message(filters.video_chat_ended)
async def voice_chat_ended(_, message: Message):
    if message.chat.id in tracker.active_calls:
        del tracker.active_calls[message.chat.id]

async def start_tracker():
    await tracker.start()

app.run(start_tracker())
