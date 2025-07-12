import os
import asyncio
import time
import requests
import yt_dlp
from youtubesearchpython.__future__ import VideosSearch
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import WebpageCurlFailed
from urllib.parse import urlparse, parse_qs

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
            print(f"[AutoDelErr] {e}")

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

async def validate_url(url: str) -> bool:
    """Validate if a URL is accessible."""
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        return r.status_code == 200
    except Exception as e:
        print(f"[URLValidationErr] {url}: {e}")
        return False

async def download_media_locally(url: str, filename: str, headers: dict = None) -> bool:
    """Download media locally and save to filename."""
    try:
        r = requests.get(url, timeout=15, stream=True, headers=headers)
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[LocalDownloadErr] {url}: {e}")
        return False

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from a URL, including music.youtube.com."""
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname or ""
    if hostname in ("youtu.be",):
        return parsed_url.path[1:]
    if hostname in ("www.youtube.com", "youtube.com", "music.youtube.com"):
        query_params = parse_qs(parsed_url.query)
        if "list" in query_params:
            return None  # Disallow playlists
        return query_params.get("v", [None])[0]
    return None

@app.on_message(filters.command(["song", "music"]))
async def download_song(_, message: Message):
    """Handle /song or /music command to download audio from YouTube or fallback API."""
    user_id = message.from_user.id
    if await check_spam(user_id):
        return await delete_message_with_delay(
            message, f"{message.from_user.mention} Slow down! Try again later."
        )

    if len(message.command) < 2:
        return await message.reply("**Please provide a song name or YouTube URL.**")

    query = " ".join(message.command[1:])
    msg = await message.reply("🔍 Searching In YouTube...")

    try:
        # Check if the query is a URL
        video_id = extract_video_id(query)
        if video_id is None and ("list=" in query.lower() or "playlist" in query.lower()):
            return await msg.edit("❌ Playlist URLs are not allowed to prevent server overload.")

        # Search using youtubesearchpython if not a valid video URL
        if not video_id:
            videos_search = VideosSearch(query, limit=1)
            res = await videos_search.next()
            videos = res.get("result", [])
            if not videos:
                return await msg.edit("❌ No results found on YouTube.")
            vid = videos[0]
            video_id = vid["id"]
            yt_url = f"https://youtube.com/watch?v={video_id}"
        else:
            yt_url = query if query.startswith("http") else f"https://youtube.com/watch?v={video_id}"
            # Fetch video info using yt_dlp to get metadata
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(yt_url, download=False)
                vid = {
                    "id": video_id,
                    "title": info.get("title", "Unknown Title")[:60],
                    "thumbnails": [{"url": info.get("thumbnail", "")}],
                    "channel": {"name": info.get("uploader", "Unknown Channel")},
                    "duration": info.get("duration_string", "0:00"),
                    "viewCount": {"text": f"{info.get('view_count', 0):,}"}
                }

        title = vid["title"]
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
            await msg.edit("⚠️ YouTube download failed. Trying fallback API...")

            # Fallback to API_URL2 for downloading MP3 directly using video ID
            try:
                if not video_id:
                    return await msg.edit("❌ Could not extract video ID for fallback API.")

                # Make request to API_URL2, expecting direct MP3 content
                r = requests.get(f"{API_URL2}?direct&id={video_id}", timeout=15, stream=True)
                r.raise_for_status()

                # Check if response is an MP3 by content-type
                content_type = r.headers.get("content-type", "").lower()
                if "audio/mpeg" not in content_type and "application/octet-stream" not in content_type:
                    return await msg.edit("❌ Fallback API did not return an MP3 file.")

                # Save the MP3 content directly
                audio_path = f"{title}.mp3"
                with open(audio_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Verify the file was written and is not empty
                if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                    return await msg.edit("❌ Failed to save MP3 from fallback API.")
            except Exception as e:
                print(f"[FallbackAPI Fail] {e}")
                return await msg.edit("❌ Failed to download audio from fallback API.")

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
            thumb=thumb_file if os.path.exists(thumb_file) else None,
            caption=f"{cap}\n\n✅ Archived Successfully."
        )

        await msg.delete()

        # Schedule deletion for user copy only
        if os.path.exists(audio_path):
            asyncio.create_task(schedule_deletion(audio_path))
        if os.path.exists(thumb_file):
            asyncio.create_task(schedule_deletion(thumb_file))

        # Schedule deletion of the sent audio message
        async def delete_audio_message():
            await asyncio.sleep(420)
            try:
                await sent.delete()
                print(f"[AutoDelete] Deleted audio message {sent.id} in chat {sent.chat.id}")
            except Exception as e:
                print(f"[DeleteAudioMsgErr] Message {sent.id}: {e}")
        asyncio.create_task(delete_audio_message())

    except Exception as e:
        print(f"[Unhandled Song Err] {e}")
        await msg.edit("❌ Something went wrong.")

@app.on_message(filters.command(["ig", "reel", "insta"], prefixes=["/", "!", "."]))
async def download_instagram(_, message: Message):
    """Handle /ig, /reel, or /insta command to download up to two Instagram media items."""
    user_id = message.from_user.id
    if await check_spam(user_id):
        return await delete_message_with_delay(
            message, f"{message.from_user.mention} Please don’t spam."
        )

    if len(message.command) < 2:
        return await message.reply("**Please provide an Instagram post/reel URL.**")

    url = message.command[1]
    msg = await message.reply("📡 Fetching Instagram media...")

    # Headers to mimic a browser request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.instagram.com/",
        "Connection": "keep-alive"
    }

    # Retry logic for Instagram API
    max_retries = 3
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            r = requests.get(f"https://ar-api-iauy.onrender.com/igsty?url={url}", timeout=15, headers=headers)
            r.raise_for_status()
            data = r.json()
            items = data.get("data", [])
            if not items:
                return await msg.edit("❌ No media found or private post.")
            break
        except Exception as e:
            print(f"[IG API Err] Attempt {attempt + 1}/{max_retries} for {url}: {e}")
            if attempt + 1 == max_retries:
                return await msg.edit("❌ Failed to fetch Instagram media after retries.")
            await asyncio.sleep(retry_delay)

    media_msgs = []
    media_count = 0
    # Process only the first two valid media items
    for media in items[0].get("media", [])[:2]:
        m_url = media.get("url")
        m_type = media.get("type")
        if not m_url or not m_type:
            print(f"[InvalidMedia] Skipping media item: url={m_url}, type={m_type}")
            continue

        # Try sending direct URL as primary method
        try:
            if m_type == "video":
                sent_msg = await message.reply_video(
                    m_url,
                    caption=f"Recreation Music Successfully ✅ Downloaded Insta Reel {m_type} from API through {url}",
                    supports_streaming=True
                )
                media_msgs.append(sent_msg)
                media_count += 1
            elif m_type == "image":
                sent_msg = await message.reply_photo(
                    m_url,
                    caption=f"Recreation Music Successfully ✅ Fetched Instagram Post {m_type} from API through {url}"
                )
                media_msgs.append(sent_msg)
                media_count += 1
        except WebpageCurlFailed:
            # Suppress logging for WebpageCurlFailed
            pass
        except Exception as e:
            print(f"[SendMediaErr] Direct {m_url}: {e}")
            # Fallback to local downloading
            local_filename = f"media_{int(time.time())}.{m_type}"
            if not await download_media_locally(m_url, local_filename, headers=headers):
                print(f"[LocalDownloadFailed] {m_url}: Failed to download media locally")
                continue

            try:
                if m_type == "video":
                    sent_msg = await message.reply_video(
                        local_filename,
                        caption=f"Downloaded Locally from Instagram {m_type} from {url}",
                        supports_streaming=True
                    )
                    media_msgs.append(sent_msg)
                    media_count += 1
                elif m_type == "image":
                    sent_msg = await message.reply_photo(
                        local_filename,
                        caption=f"Locally Downloaded from Instagram {m_type} from {url}"
                    )
                    media_msgs.append(sent_msg)
                    media_count += 1
                # Schedule local file deletion
                if os.path.exists(local_filename):
                    asyncio.create_task(schedule_deletion(local_filename))
            except Exception as e:
                print(f"[SendMediaErr] Local {local_filename}: {e}")
                if os.path.exists(local_filename):
                    asyncio.create_task(schedule_deletion(local_filename))
                continue

        # Stop after sending two media items
        if media_count >= 2:
            break

    if not media_msgs:
        return await msg.edit("❌ No valid media could be sent.")

    await msg.delete()

    # Schedule deletion of user-shared files (applies to both group and DMs)
    async def delete_instagram_messages():
        await asyncio.sleep(420)
        for m in media_msgs:
            try:
                await m.delete()
                print(f"[AutoDelete] Deleted message {m.id} in chat {m.chat.id}")
            except Exception as e:
                print(f"[DeleteMediaErr] Message {m.id} in chat {m.chat.id}: {e}")
    asyncio.create_task(delete_instagram_messages())
