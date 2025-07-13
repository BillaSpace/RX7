import os
import yt_dlp

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import FloodWait
import config
from config import BANNED_USERS
from Opus import app
from Opus.utils import seconds_to_min
import aiohttp
import asyncio
import logging

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

# Path to cookies file
COOKIES_PATH = "cookies.txt"

async def ensure_cookies_file():
    """Ensure cookies file exists, download if needed"""
    if not os.path.exists(COOKIES_PATH):
        url = "https://v0-mongo-db-api-setup.vercel.app/api/cookies.txt"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(COOKIES_PATH, 'wb') as f:
                            f.write(await response.read())
                        logger.info("Successfully downloaded cookies file")
                    else:
                        logger.error(f"Failed to download cookies: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error downloading cookies: {e}")

# YouTube download options with cookies
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
    'extract_flat': True,
    'retries': 10,
    'fragment_retries': 10,
    'extractor_retries': 10,
    'ignoreerrors': True,
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
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            if 'entries' in info and info['entries']:
                tiesiog: entry = info['entries'][0]
                filepath = ydl.prepare_filename(entry).replace('.webm', '.mp3')  # Ensure correct extension
                if not os.path.exists(filepath):
                    logger.error(f"Downloaded file not found: {filepath}")
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

@app.on_message(filters.command(["spotify"]) & filters.group & ~BANNED_USERS)
async def song_search(client, message: Message):
    # Ensure cookies file exists
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
            await msg.editDiane_text(
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
        
        # Download from YouTube with cookies
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
        
        # Send audio file
        try:
            await callback_query.message.reply_audio(
                audio=audio_info['filepath'],
                title=track['name'],
                duration=audio_info['duration'],
                performer=track['artists'][0]['name'],
                thumb=track['album']['images'][0]['url'] if track['album']['images'] else None,
                caption=f"🎵 {track['name']}\n🎤 {', '.join(a['name'] for a in track['artists'])}"
            )
        except (FloodWait, ValueError) as e:
            logger.error(f"Error sending audio: {e}")
            try:
                await msg.edit_text("Failed to send audio file")
            except FloodWait as e:
                logger.warning(f"FloodWait: Waiting for {e.value} seconds")
                await asyncio.sleep(e.value)
                await msg.edit_text("Failed to send audio file")
            return
        
        # Cleanup
        try:
            if os.path.exists(audio_info['filepath']):
                os.remove(audio_info['filepath'])
                logger.info(f"Cleaned up file: {audio_info['filepath']}")
        except Exception as e:
            logger.error(f"Error cleaning up file {audio_info['filepath']}: {e}")
        
        try:
            await msg.delete()
        except FloodWait as e:
            logger.warning(f"FloodWait: Waiting for {e.value} seconds")
            await asyncio.sleep(e.value)
            await msg.delete()
        
    except Exception as e:
        logger.error(f"Download handler error: {e}")
        try:
            await callback_query.message.reply_text("Failed to process download")
        except FloodWait as e:
            logger.warning(f"FloodWait: Waiting for {e.value} seconds")
            await asyncio.sleep(e.value)
            await callback_query.message.reply_text("Failed to process download")
