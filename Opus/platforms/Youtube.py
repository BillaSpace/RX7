import asyncio
import os
import re
import json
from typing import Union, Tuple, Optional, List, Dict
import base64
import glob
import random
import logging
import aiofiles
import aiohttp

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cookie_txt_file() -> str:
    """Get a random cookie file from the cookies directory."""
    try:
        folder_path = os.path.join(os.getcwd(), "cookies")
        os.makedirs(folder_path, exist_ok=True)
        
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        if not txt_files:
            raise FileNotFoundError("No cookie files found in cookies directory")
        
        cookie_file = random.choice(txt_files)
        log_file = os.path.join(folder_path, "logs.csv")
        
        with open(log_file, 'a') as f:
            f.write(f'Selected cookie file: {cookie_file}\n')
            
        return cookie_file
    except Exception as e:
        logger.error(f"Error in cookie_txt_file: {e}")
        raise

async def check_file_size(link: str) -> Optional[int]:
    """Check the total file size of all formats for a YouTube link."""
    async def get_format_info(link: str) -> Optional[dict]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "-J",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.error(f"yt-dlp error: {stderr.decode().strip()}")
                return None
                
            return json.loads(stdout.decode())
        except Exception as e:
            logger.error(f"Error getting format info: {e}")
            return None

    try:
        info = await get_format_info(link)
        if not info:
            return None
            
        formats = info.get('formats', [])
        if not formats:
            logger.warning("No formats available for this video")
            return None
            
        total_size = 0
        for fmt in formats:
            if isinstance(fmt, dict) and fmt.get('filesize'):
                try:
                    total_size += int(fmt['filesize'])
                except (TypeError, ValueError):
                    continue
                    
        return total_size if total_size > 0 else None
    except Exception as e:
        logger.error(f"Error in check_file_size: {e}")
        return None

async def shell_cmd(cmd: str) -> str:
    """Execute a shell command and return its output."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode('utf-8').strip()
            if "unavailable videos are hidden" in error_msg.lower():
                return stdout.decode('utf-8').strip()
            raise RuntimeError(error_msg)
            
        return stdout.decode('utf-8').strip()
    except Exception as e:
        logger.error(f"Command failed: {cmd} - Error: {e}")
        raise

class YouTubeAPI:
    """Main YouTube API handler with both cookie-based and API downloads."""
    
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        
        # Audio API endpoint (base64 encoded)
        self._audio_api = base64.b64decode(
            "aHR0cHM6Ly9iaWxsYWF4LnNodWtsYWt1c3VtNHEud29ya2Vycy5kZXYvYXJ5dG1wMz9kaXJlY3QmaWQ9"
        ).decode('utf-8')

    async def exists(self, link: str, videoid: bool = False) -> bool:
        """Check if a YouTube link exists."""
        try:
            if videoid:
                link = self.base + link
            return bool(re.search(self.regex, link))
        except Exception as e:
            logger.error(f"Error checking link existence: {e}")
            return False

    async def url(self, message: Message) -> Optional[str]:
        """Extract URL from a Pyrogram message."""
        try:
            messages = [message]
            if message.reply_to_message:
                messages.append(message.reply_to_message)
                
            for msg in messages:
                # Check entities first
                if msg.entities:
                    for entity in msg.entities:
                        if entity.type == MessageEntityType.URL:
                            text = msg.text or msg.caption
                            if text:
                                return text[entity.offset:entity.offset + entity.length]
                
                # Check caption entities if no URL found
                if msg.caption_entities:
                    for entity in msg.caption_entities:
                        if entity.type == MessageEntityType.TEXT_LINK:
                            return entity.url
                            
            return None
        except Exception as e:
            logger.error(f"Error extracting URL: {e}")
            return None

    async def details(self, link: str, videoid: bool = False) -> Tuple[str, str, int, str, str]:
        """Get video details (title, duration, thumbnail, etc.)."""
        default_return = ("", "0:00", 0, "", "")
        
        try:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
                
            results = VideosSearch(link, limit=1)
            search_result = await results.next()
            
            if not search_result or not search_result.get("result"):
                logger.warning("No results found for video details")
                return default_return
                
            result = search_result["result"][0]
            title = result.get("title", "")
            duration_min = result.get("duration", "0:00")
            thumbnails = result.get("thumbnails", [{}])
            thumbnail = thumbnails[0].get("url", "").split("?")[0] if thumbnails else ""
            vidid = result.get("id", "")
            
            duration_sec = 0 if str(duration_min) == "None" else time_to_seconds(duration_min)
            
            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            logger.error(f"Error getting video details: {e}")
            return default_return

    async def title(self, link: str, videoid: bool = False) -> str:
        """Get video title."""
        try:
            title, *_ = await self.details(link, videoid)
            return title
        except Exception as e:
            logger.error(f"Error getting title: {e}")
            return ""

    async def duration(self, link: str, videoid: bool = False) -> str:
        """Get video duration."""
        try:
            _, duration, *_ = await self.details(link, videoid)
            return duration
        except Exception as e:
            logger.error(f"Error getting duration: {e}")
            return "0:00"

    async def thumbnail(self, link: str, videoid: bool = False) -> str:
        """Get video thumbnail URL."""
        try:
            *_, thumbnail, _ = await self.details(link, videoid)
            return thumbnail
        except Exception as e:
            logger.error(f"Error getting thumbnail: {e}")
            return ""

    async def video(self, link: str, videoid: bool = False) -> Tuple[int, str]:
        """Get direct video URL."""
        try:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
                
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                return 1, stdout.decode().split("\n")[0]
            return 0, stderr.decode()
        except Exception as e:
            logger.error(f"Error getting video URL: {e}")
            return 0, str(e)

    async def playlist(self, link: str, limit: int, user_id: int, videoid: bool = False) -> List[str]:
        """Get list of video IDs from a playlist."""
        try:
            if videoid:
                link = self.listbase + link
            if "&" in link:
                link = link.split("&")[0]
                
            cmd = (
                f"yt-dlp -i --get-id --flat-playlist "
                f"--cookies {cookie_txt_file()} "
                f"--playlist-end {limit} --skip-download {link}"
            )
            playlist = await shell_cmd(cmd)
            
            return [vid for vid in playlist.split("\n") if vid.strip()]
        except Exception as e:
            logger.error(f"Error getting playlist: {e}")
            return []

    async def track(self, link: str, videoid: bool = False) -> Tuple[Dict[str, str], str]:
        """Get track details."""
        default_return = ({
            "title": "",
            "link": "",
            "vidid": "",
            "duration_min": "0:00",
            "thumb": ""
        }, "")
        
        try:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
                
            results = VideosSearch(link, limit=1)
            search_result = await results.next()
            
            if not search_result or not search_result.get("result"):
                logger.warning("No results found for track details")
                return default_return
                
            result = search_result["result"][0]
            track_details = {
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "vidid": result.get("id", ""),
                "duration_min": result.get("duration", "0:00"),
                "thumb": result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
            }
            
            return track_details, track_details["vidid"]
        except Exception as e:
            logger.error(f"Error getting track details: {e}")
            return default_return

    async def formats(self, link: str, videoid: bool = False) -> Tuple[List[Dict[str, str]], str]:
        """Get available formats for a video."""
        try:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
                
            ytdl_opts = {
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True
            }
            
            formats_available = []
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                
                for fmt in info.get("formats", []):
                    try:
                        if "dash" in str(fmt.get("format", "")).lower():
                            continue
                            
                        formats_available.append({
                            "format": fmt.get("format", ""),
                            "filesize": fmt.get("filesize", 0),
                            "format_id": fmt.get("format_id", ""),
                            "ext": fmt.get("ext", ""),
                            "format_note": fmt.get("format_note", ""),
                            "yturl": link,
                        })
                    except Exception:
                        continue
                        
            return formats_available, link
        except Exception as e:
            logger.error(f"Error getting formats: {e}")
            return [], link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: bool = False
    ) -> Tuple[str, str, str, str]:
        """Get slider details for query results."""
        default_return = ("", "0:00", "", "")
        
        try:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
                
            search = VideosSearch(link, limit=10)
            result = (await search.next()).get("result", [])
            
            if not result or query_type >= len(result):
                logger.warning("No results found for slider")
                return default_return
                
            item = result[query_type]
            return (
                item.get("title", ""),
                item.get("duration", "0:00"),
                item.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
                item.get("id", "")
            )
        except Exception as e:
            logger.error(f"Error getting slider details: {e}")
            return default_return

    async def _download_audio_from_api(self, video_id: str) -> Optional[str]:
        """Download audio from external API."""
        file_path = os.path.join("downloads", f"{video_id}.mp3")
        
        try:
            if os.path.exists(file_path):
                return file_path
                
            api_url = f"{self._audio_api}{video_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status != 200:
                        logger.error(f"API request failed with status {response.status}")
                        return None
                        
                    os.makedirs("downloads", exist_ok=True)
                    
                    async with aiofiles.open(file_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            await f.write(chunk)
                            
            return file_path
        except Exception as e:
            logger.error(f"Error downloading from API: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return None

    async def download(
        self,
        link: str,
        mystic,
        video: bool = False,
        videoid: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Tuple[Optional[str], bool]:
        """Main download method with multiple download options."""
        try:
            if videoid:
                link = self.base + link
                
            loop = asyncio.get_running_loop()

            def audio_dl() -> str:
                """Download audio using yt-dlp."""
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    file_path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                    if not os.path.exists(file_path):
                        ydl.download([link])
                    return file_path

            def video_dl() -> str:
                """Download video using yt-dlp."""
                ydl_opts = {
                    "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    file_path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                    if not os.path.exists(file_path):
                        ydl.download([link])
                    return file_path

            # Handle song video download
            if songvideo:
                if not title or not format_id:
                    raise ValueError("Title and format_id are required for song video download")
                
                def song_video_dl():
                    ydl_opts = {
                        "format": f"{format_id}+140",
                        "outtmpl": f"downloads/{title}",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                        "no_warnings": True,
                        "cookiefile": cookie_txt_file(),
                        "prefer_ffmpeg": True,
                        "merge_output_format": "mp4",
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([link])
                
                await loop.run_in_executor(None, song_video_dl)
                return f"downloads/{title}.mp4", True

            # Handle song audio download
            elif songaudio:
                if not title or not format_id:
                    raise ValueError("Title and format_id are required for song audio download")
                
                def song_audio_dl():
                    ydl_opts = {
                        "format": format_id,
                        "outtmpl": f"downloads/{title}.%(ext)s",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                        "no_warnings": True,
                        "cookiefile": cookie_txt_file(),
                        "prefer_ffmpeg": True,
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }],
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([link])
                
                await loop.run_in_executor(None, song_audio_dl)
                return f"downloads/{title}.mp3", True

            # Handle regular video download
            elif video:
                if await is_on_off(1):
                    # Direct download
                    downloaded_file = await loop.run_in_executor(None, video_dl)
                    return downloaded_file, True
                else:
                    # Try to get stream URL first
                    proc = await asyncio.create_subprocess_exec(
                        "yt-dlp",
                        "--cookies", cookie_txt_file(),
                        "-g",
                        "-f",
                        "best[height<=?720][width<=?1280]",
                        link,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()
                    
                    if proc.returncode == 0 and stdout:
                        return stdout.decode().strip().split("\n")[0], False
                    
                    # Fallback to direct download if streaming fails
                    file_size = await check_file_size(link)
                    if file_size is None:
                        logger.error("Failed to get file size")
                        return None, False
                    
                    if (file_size / (1024 * 1024)) > 250:
                        logger.error("File size exceeds limit (250MB)")
                        return None, False
                    
                    downloaded_file = await loop.run_in_executor(None, video_dl)
                    return downloaded_file, True
            else:
                # Try audio API first
                video_id = self._extract_video_id(link)
                if video_id:
                    api_file = await self._download_audio_from_api(video_id)
                    if api_file:
                        return api_file, True
                
                # Fallback to cookie-based download
                downloaded_file = await loop.run_in_executor(None, audio_dl)
                return downloaded_file, True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None, False

    def _extract_video_id(self, link: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|v/|watch\?v=))([0-9A-Za-z_-]{11})",
            r"youtube\.com/watch\?.*v=([0-9A-Za-z_-]{11})",
            r"youtu\.be/([0-9A-Za-z_-]{11})"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        return None
