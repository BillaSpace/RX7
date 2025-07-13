import os
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import FloodWait, MessageNotModified, MessageIdInvalid
from config import BANNED_USERS, SONG_DUMP_ID
from Opus import app
from Opus.utils import seconds_to_min
import aiohttp
import asyncio
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPOTIFY_CLIENT_ID = "2d3fd5ccdd3d43dda6f17864d8eb7281"
SPOTIFY_CLIENT_SECRET = "48d311d8910a4531ae81205e1f754d27"

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Path to cookies file and downloads directory
COOKIES_PATH = "cookies/cookies.txt"
DOWNLOADS_DIR = "downloads/"

async def ensure_cookies_file():
    """Ensure cookies file exists, download if needed"""
    if not os.path.exists(COOKIES_PATH):
        url = "https://v0-mongo-db-api-setup.vercel.app/api/cookies.txt"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(COOKIES_PATH, 'wb') as f:
                            f.write(content)
                        logger.info(f"Successfully downloaded cookies file. Size: {len(content)} bytes")
                    else:
                        logger.error(f"Failed to download cookies: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error downloading cookies: {e}")
    else:
        logger.info(f"Cookies file already exists: {COOKIES_PATH}")

async def cleanup_downloads():
    """Clean up files in downloads/ folder older than 60 minutes"""
    try:
        current_time = time.time()
        for filename in os.listdir(DOWNLOADS_DIR):
            filepath = os.path.join(DOWNLOADS_DIR, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > 3600:  # 60 minutes
                    try:
                        os.remove(filepath)
                        logger.info(f"Cleaned up old file: {filepath}")
                    except Exception as e:
                        logger.error(f"Error cleaning up file {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error during downloads cleanup: {e}")

# YouTube download options
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
    'cookiefile': COOKIES_PATH,
    'extract_flat': False,
    'retries': 10,
    'fragment_retries': 10,
    'extractor_retries': 10,
    'ignoreerrors': False,
    'no_check_certificates': True,
    'geo_bypass': True,
    'force_ipv4': True,
    'noplaylist': True
}

async def search_spotify(query, limit=5):
    """Search songs on Spotify"""
    try:
        results = sp.search(q=query, limit=limit, type='track')
        return results['tracks']['items']
    except Exception as e:
        logger.error(f"Spotify search error: {e}")
        return []

async def download_youtube_audio(query):
    """Download audio from YouTube with cookies"""
    # Generate expected filename
    sanitized_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
    expected_filename = f"downloads/{sanitized_query}.mp3"
    
    # Check if file already exists
    if os.path.exists(expected_filename):
        logger.info(f"File already exists, skipping download: {expected_filename}")
        try:
            entry = {'title': sanitized_query, 'duration': 0, 'uploader': 'Unknown Artist', 'thumbnail': ''}
            return {
                'filepath': expected_filename,
                'title': entry.get('title', 'Unknown Track'),
                'duration': entry.get('duration', 0),
                'artist': entry.get('uploader', 'Unknown Artist'),
                'thumbnail': entry.get('thumbnail', '')
            }
        except Exception as e:
            logger.error(f"Error accessing existing file {expected_filename}: {e}")
            return None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            if 'entries' not in info or not info['entries']:
                logger.error(f"No results found for query '{query}'")
                return None
            entry = info['entries'][0]
            filepath = ydl.prepare_filename(entry)
            filepath = filepath.rsplit('.', 1)[0] + '.mp3'
            if not os.path.exists(filepath):
                logger.error(f"Downloaded file not found: {filepath}")
                # Retry without cookies
                ydl_opts_no_cookies = ydl_opts.copy()
                ydl_opts_no_cookies.pop('cookiefile', None)
                with yt_dlp.YoutubeDL(ydl_opts_no_cookies) as ydl:
                    info = ydl.extract_info(f"ytsearch:{query}", download=True)
                    if 'entries' not in info or not info['entries']:
                        logger.error(f"Retry without cookies failed for query '{query}'")
                        return None
                    entry = info['entries'][0]
                    filepath = ydl.prepare_filename(entry)
                    filepath = filepath.rsplit('.', 1)[0] + '.mp3'
                    if not os.path.exists(filepath):
                        logger.error(f"Retry downloaded file not found: {filepath}")
                        return None
            return {
                'filepath': filepath,
                'title': entry.get('title', 'Unknown Track'),
                'duration': entry.get('duration', 0),
                'artist': entry.get('uploader', 'Unknown Artist'),
                'thumbnail': entry.get('thumbnail', '')
            }
    except Exception as e:
        logger.error(f"YouTube download error for query '{query}': {e}")
        return None

async def auto_delete_message(message: Message, delay=300):
    """Delete a message after a specified delay (default 5 minutes)"""
    try:
        await asyncio.sleep(delay)
        try:
            await message.delete()
            logger.info(f"Deleted message {message.id} in chat {message.chat.id}")
        except MessageIdInvalid:
            logger.warning(f"Message {message.id} in chat {message.chat.id} already deleted or invalid")
        except Exception as e:
            logger.error(f"Error deleting message {message.id} in chat {message.chat.id}: {e}")
    except asyncio.CancelledError:
        logger.info(f"Auto-delete task for message {message.id} cancelled")
    except Exception as e:
        logger.error(f"Error in auto-delete task for message {message.id}: {e}")

@app.on_message(filters.command(["spotify"]) & filters.group & ~BANNED_USERS)
async def song_search(client, message: Message):
    await ensure_cookies_file()
    
    try:
        if len(message.command) < 2:
            return await message.reply_text("Please provide a song name to search")
        
        query = " ".join(message.command[1:])
        msg = await message.reply_text(f"🔍 Searching for: {query}")
        
        results = await search_spotify(query)
        if not results:
            return await msg.edit_text("No results found")
        
        buttons = []
        for idx, track in enumerate(results, 1):
            artists = ", ".join([a['name'] for a in track['artists']])
            duration = seconds_to_min(track['duration_ms'] // 1000)
            buttons.append([
                InlineKeyboardButton(
                    f"{idx}. {track['name'][:20]} - {artists[:15]} ({duration})",
                    callback_data=f"dl_{track['id']}"
                )
            ])
        
        try:
            await msg.edit_text(
                f"🎵 Search Results for: {query}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except FloodWait as e:
            logger.warning(f"FloodWait: Waiting for {e.value} seconds")
            await asyncio.sleep(e.value)
            await msg.edit_text(
                f"🎵 Search Results for: {query}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
        logger.error(f"Search error: {e}")
        try:
            await msg.edit_text("Failed to search for songs")
        except FloodWait as e:
            logger.warning(f"FloodWait: Waiting for {e.value} seconds")
            await asyncio.sleep(e.value)
            await msg.edit_text("Failed to search for songs")

@app.on_callback_query(filters.regex(r"^dl_(.+)$"))
async def download_handler(client, callback_query):
    try:
        await callback_query.answer("Preparing download...")
        
        track_id = callback_query.matches[0].group(1)
        track = sp.track(track_id)
        query = f"{track['name']} {track['artists'][0]['name']}"
        
        msg = await callback_query.message.reply_text(f"⬇️ Downloading: {query}")
        
        # Ensure downloads directory exists
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        
        # Download audio
        audio_info = await download_youtube_audio(query)
        if not audio_info or not os.path.exists(audio_info['filepath']):
            logger.error(f"Audio file missing: {audio_info.get('filepath') if audio_info else 'None'}")
            try:
                await msg.edit_text("Failed to download song")
            except FloodWait as e:
                logger.warning(f"FloodWait: Waiting for {e.value} seconds")
                await asyncio.sleep(e.value)
                await msg.edit_text("Failed to download song")
            return
        
        try:
            # Send audio to the original chat
            audio_message = await callback_query.message.reply_audio(
                audio=audio_info['filepath'],
                title=track['name'],
                duration=audio_info['duration'],
                performer=RecreationMusic['artists'][0]['name'],
                thumb=track['album']['images'][0]['url'] if track['album']['images'] else None,
                caption=f"🎵 {track['name']}\n🎤 {', '.join(a['name'] for a in track['artists'])}"
            )
            
            # Schedule auto-delete for the audio message (except in SONG_DUMP_ID)
            if callback_query.message.chat.id != SONG_DUMP_ID:
                asyncio.create_task(auto_delete_message(audio_message, delay=300))
            
            # Send a copy to SONG_DUMP_ID
            if SONG_DUMP_ID:
                try:
                    await app.send_audio(
                        chat_id=SONG_DUMP_ID,
                        audio=audio_info['filepath'],
                        title=track['name'],
                        duration=audio_info['duration'],
                        performer=track['artists'][0]['name'],
                        thumb=track['album']['images'][0]['url'] if track['album']['images'] else None,
                        caption=f"🎵 {track['name']}\n🎤 {', '.join(a['name'] for a in track['artists'])} (Shared from {callback_query.message.chat.title or callback_query.message.chat.id})"
                    )
                    logger.info(f"Sent audio to SONG_DUMP_ID: {SONG_DUMP_ID}")
                except Exception as e:
                    logger.error(f"Error sending audio to SONG_DUMP_ID: {e}")
            
        except (FloodWait, ValueError) as e:
            logger.error(f"Error sending audio: {e}")
            try:
                await msg.edit_text("Failed to send audio file")
            except FloodWait as e:
                logger.warning(f"FloodWait: Waiting for {e.value} seconds")
                await asyncio.sleep(e.value)
                await msg.edit_text("Failed to send audio file")
            return
        
        # Clean up the downloading message
        try:
            await msg.delete()
        except FloodWait as e:
            logger.warning(f"FloodWait: Waiting for {e.value} seconds")
            await asyncio.sleep(e.value)
            await msg.delete()
        
        # Schedule cleanup of downloads folder
        asyncio.create_task(cleanup_downloads())
        
        # Clean up the downloaded file (unless it's in SONG_DUMP_ID context)
        try:
            if os.path.exists(audio_info['filepath']) and callback_query.message.chat.id != SONG_DUMP_ID:
                os.remove(audio_info['filepath'])
                logger.info(f"Cleaned up file: {audio_info['filepath']}")
        except Exception as e:
            logger.error(f"Error cleaning up file {audio_info['filepath']}: {e}")
        
    except Exception as e:
        logger.error(f"Download handler error: {e}")
        try:
            await callback_query.message.reply_text("Failed to process download")
        except FloodWait as e:
            logger.warning(f"FloodWait: Waiting for {e.value} seconds")
            await asyncio.sleep(e.value)
            await callback_query.message.reply_text("Failed to process download")
