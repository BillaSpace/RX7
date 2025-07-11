import os
import asyncio
import time
import requests
import yt_dlp
from youtubesearchpython.__future__ import VideosSearch  # Updated import
from pyrogram import Client, filters
from pyrogram.types import Message

from Opus import app
from config import SONG_DUMP_ID, API_URL2  # Ensure these are defined

# Spam control settings
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5
user_last_message_time = {}
user_command_count = {}

async def check_spam(user_id: int) -> bool:
    """Check if user is spamming based on command frequency."""
    now = time.time()
    last = user_last_message_time.get(user_id, 0)
    if now - last < SPAM_WINDOW_SECONDS:
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            user_last_message_time[user_id] = now
            return True
    else:
        user_command_count[user_id] = 1
    user_last_message_time[user_id] = now
    return False

async def delete_message_with_delay(message: Message, text: str, delay: int = 3):
    """Send a temporary reply and delete it after a delay."""
    msg = await message.reply_text(text)
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception as e:
        print(f"[DeleteMsgErr] {e}")

async def schedule_deletion(file_path: str, delay: int = 420):
    """Schedule file deletion after a delay."""
    await asyncio.sleep(delay)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[AutoDelete] {file_path} deleted")
        except Exception as e:
            print F"[AutoDelErr] {e}"

async def download_thumbnail(url: str, filename: str) -> bool:
    """Download a thumbnail from a URL."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"[ThumbErr] {e}")
        return False

@app.on_message(filters.command(["song", "music"]))
async def download_song(_, message: Message):
    """Handle /song or /music command to download audio from YouTube or fallback API."""
    user_id = message.from_user.id
    if await check_spam(user_id):
        return await delete_message_with_delay(
            message, f"**{message.from_user.mention} Slow down! Try again later.**"
        )

    if len(message.command) < 2:
        return await message.reply("**Please provide a song name.**")

    query = " ".join(message.command[1:])
    msg = await message.reply("🔍 Searching YouTube...")

    try:
        # Asynchronous YouTube search using youtubesearchpython.__future__
        videos_search = VideosSearch(query, limit=1)
        res = await videos_search.next()
        videos = res.get("result", [])
        if not videos:
            return await msg.edit("❌ No results found.")

        vid = videos[0]
        yt_url = f"https://youtube.com/watch?v={vid['id']}"
        title = vid["title"][:60]
        thumb_url = vid["thumbnails"][0]["url"] if vid.get("thumbnails") else ""
        channel = vid.get("channel", {}).get("name", "Unknown Channel")
        duration = vid.get("duration", "0:00")
        views = vid.get("viewCount", {}).get("text", "N/A")
        d_sec = sum(int(x) * 60**i for i, x in enumerate(reversed(duration.split(":"))))

        # Download thumbnail
        thumb_file = f"{title}.jpg"
        if thumb_url:
            await download_thumbnail(thumb_url, thumb_file)

        # yt_dlp configuration
        cookie_file = "cookies/cookies.txt"
        if not os.path.exists(cookie_file):
            print(f"[CookieErr] Cookie file {cookie_file} not found")
            await msg.edit("⚠️ Cookie file missing. Trying without cookies...")

        ydl_opts = {
            "format": "bestaudio[ext=m4a]",
            "quiet": True,
            "cookiefile": cookie_file if os.path.exists(cookie_file) else None,
            "noplaylist": True,
            "outtmpl": f"{title}.%(ext)s",
        }

        audio_path = None
        await msg.edit("📥 Downloading from YouTube...")

        # Try downloading with yt_dlp
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_url, download=True)
                audio_path = ydl.prepare_filename(info)
        except Exception as e:
            print(f"[YTDLP Fail] {e}")
            await msg.edit("⚠️ YouTube download failed. Trying fallback...")

            # Fallback to API_URL2 for downloading audio file
            r = requests.get(f"{API_URL2}?query={query}", timeout=15)
            r.raise_for_status()
            data = r.json()
            url2 = data.get("audio_url")
            if not url2:
                return await msg.edit("❌ Fallback API returned no audio.")

            audio_path = f"{title}.mp3"
            with open(audio_path, "wb") as f:
                f.write(requests.get(url2, timeout=15).content)

        # Prepare caption
        cap = (
            f"**{title}**\n"
            f"➤ Performer: Recreation Music\n"
            f"➤ Artist: Unknown\n"
            f"➤ Channel: {channel}\n"
            f"➤ Link: {yt_url}\n"
            f"➤ Views: {views}\n\n"
            f"Co-powered by: 🌌 Space-X Ashlyn API\n"
            f"Requested by: {message.from_user.mention}"
        )

        await msg.edit("📤 Uploading now...")

        # Send to user
        sent = await message.reply_audio(
            audio=audio_path,
            title=title,
            performer="Recreation Music",
            duration=d_sec,
            thumb=thumb_file if os.path.exists(thumb_file) else None,
            caption=cap
        )

        # Send to dump channel (no deletion for dump)
        await app.send_audio(
            SONG_DUMP_ID,
            audio=audio_path,
            title=title,
            performer="Recreation Music",
            duration=d_sec,
            thumb=thumb_file if os.path.exists(thumb salted fish
            thumb_file,
            caption=f"{cap}\n\n✅ Archived Successfully."
        )

        await msg.delete()

        # Schedule deletion for user copy only
        asyncio.create_task(schedule_deletion(audio_path))
        if os.path.exists(thumb_file):
            asyncio.create_task(schedule_deletion(thumb_file))

    except Exception as e:
        print(f"[Unhandled Song Err] {e}")
        await msg.edit("❌ Something went wrong.")

@app.on_message(filters.command(["ig", "reel", "insta"], prefixes=["/", "!", "."]))
async def download_instagram(_, message: Message):
    """Handle /ig, /reel, or /insta command to download Instagram media."""
    user_id = message.from_user.id
    if await check_spam(user_id):
        return await delete_message_with_delay(
            message, f"**{message.from_user.mention} Please don’t spam.**"
        )

    if len(message.command) < 2:
        return await message.reply("**Please provide an Instagram post/reel URL.**")

    url = message.command[1]
    msg = await message.reply("📡 Fetching Instagram media...")

    try:
        r = requests.get(f"https://ar-api-iauy.onrender.com/igsty?url={url}", timeout=15)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", [])
        if not items:
            return await msg.edit("❌ No media found or private post.")

        media_msgs = []

        for media in items[0].get("media", []):
            m_url = media.get("url")
            m_type = media.get("type")
            if not m_url or not m_type:
                continue
            if m_type == "video":
                media_msgs.append(await message.reply_video(m_url))
            elif m_type == "image":
                media_msgs.append(await message.reply_photo(m_url))

        await msg.delete()

        # Schedule deletion of user-shared files (only replies, not dump)
        async def delete_instas():
            await asyncio.sleep(420)
            for m in media_msgs:
                try:
                    await m.delete()
                except Exception:
                    pass
        asyncio.create_task(delete_instas())

    except Exception as e:
        print(f"[IG Err] {e}")
        await msg.edit("❌ Failed to download Instagram media.")
