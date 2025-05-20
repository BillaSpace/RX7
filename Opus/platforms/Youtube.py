import asyncio
import os
import re
import json
from typing import Union
import base64
import hashlib

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds

import glob
import random
import logging
import aiohttp

# Obfuscated function names and variables
_obfuscate = lambda x: hashlib.md5(x.encode()).hexdigest()[:8]
_cookie_func = _obfuscate("cookie_selector")
_check_size = _obfuscate("file_size_checker")
_shell_exec = _obfuscate("execute_shell")

def _get_cookie_path():
    _folder = f"{os.getcwd()}/cookies"
    _log_file = f"{os.getcwd()}/cookies/logs.csv"
    _files = glob.glob(os.path.join(_folder, '*.txt'))
    if not _files:
        raise FileNotFoundError("No cookie files available")
    _selected = random.choice(_files)
    with open(_log_file, 'a') as f:
        f.write(f'Selected: {_selected}\n')
    return f"cookies/{str(_selected).split('/')[-1]}"

async def _verify_size(link):
    async def _get_info():
        _cmd = [
            "yt-dlp",
            "--cookies", _get_cookie_path(),
            "-J",
            link
        ]
        _proc = await asyncio.create_subprocess_exec(
            *_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _out, _err = await _proc.communicate()
        return json.loads(_out.decode()) if _proc.returncode == 0 else None

    _data = await _get_info()
    if not _data:
        return None
    
    return sum(f.get('filesize', 0) for f in _data.get('formats', []))

async def _run_shell(cmd):
    _proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _out, _err = await _proc.communicate()
    return _out.decode() if not _err else _err.decode()

class _YouTubeHandler:
    def __init__(self):
        self._video_base = "".join([
            chr(104), chr(116), chr(116), chr(112), chr(115), chr(58),
            chr(47), chr(47), chr(119), chr(119), chr(119), chr(46),
            chr(121), chr(111), chr(117), chr(116), chr(117), chr(98),
            chr(101), chr(46), chr(99), chr(111), chr(109), chr(47),
            chr(119), chr(97), chr(116), chr(99), chr(104), chr(63),
            chr(118), chr(61)
        ])
        self._regex_pattern = r"(?:youtube\.com|youtu\.be)"
        self._list_base = "".join([
            chr(104), chr(116), chr(116), chr(112), chr(115), chr(58),
            chr(47), chr(47), chr(121), chr(111), chr(117), chr(116),
            chr(117), chr(98), chr(101), chr(46), chr(99), chr(111),
            chr(109), chr(47), chr(112), chr(108), chr(97), chr(121),
            chr(108), chr(105), chr(115), chr(116), chr(63), chr(108),
            chr(105), chr(115), chr(116), chr(61)
        ])

    async def _validate_link(self, link: str, is_video_id: bool = False):
        if is_video_id:
            link = self._video_base + link
        return bool(re.search(self._regex_pattern, link))

    async def _extract_url(self, message: Message):
        _msgs = [message]
        if message.reply_to_message:
            _msgs.append(message.reply_to_message)
        
        for _msg in _msgs:
            if _msg.entities:
                for _ent in _msg.entities:
                    if _ent.type == MessageEntityType.URL:
                        return (_msg.text or _msg.caption)[_ent.offset:_ent.offset + _ent.length]
            elif _msg.caption_entities:
                for _ent in _msg.caption_entities:
                    if _ent.type == MessageEntityType.TEXT_LINK:
                        return _ent.url
        return None

    async def _get_metadata(self, link: str, is_video_id: bool = False):
        if is_video_id:
            link = self._video_base + link
        if "&" in link:
            link = link.split("&")[0]
        
        _results = VideosSearch(link, limit=1)
        _data = (await _results.next())["result"][0]
        
        _duration = _data["duration"]
        return (
            _data["title"],
            _duration,
            int(time_to_seconds(_duration)) if _duration != "None" else 0,
            _data["thumbnails"][0]["url"].split("?")[0],
            _data["id"]
        )

    async def _get_stream_url(self, link: str, is_video_id: bool = False):
        if is_video_id:
            link = self._video_base + link
        if "&" in link:
            link = link.split("&")[0]
            
        _proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", _get_cookie_path(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, _err = await _proc.communicate()
        return (1, _out.decode().split("\n")[0]) if _out else (0, _err.decode())

    async def _process_playlist(self, link, limit, is_video_id: bool = False):
        if is_video_id:
            link = self._list_base + link
        if "&" in link:
            link = link.split("&")[0]
            
        _output = await _run_shell(
            f"yt-dlp -i --get-id --flat-playlist --cookies {_get_cookie_path()} "
            f"--playlist-end {limit} --skip-download {link}"
        )
        return [x for x in _output.split("\n") if x]

    async def _get_track_info(self, link: str, is_video_id: bool = False):
        if is_video_id:
            link = self._video_base + link
        if "&" in link:
            link = link.split("&")[0]
            
        _results = VideosSearch(link, limit=1)
        _data = (await _results.next())["result"][0]
        return {
            "title": _data["title"],
            "link": _data["link"],
            "vidid": _data["id"],
            "duration_min": _data["duration"],
            "thumb": _data["thumbnails"][0]["url"].split("?")[0],
        }, _data["id"]

    async def _get_formats(self, link: str, is_video_id: bool = False):
        if is_video_id:
            link = self._video_base + link
        if "&" in link:
            link = link.split("&")[0]
            
        _ydl_opts = {
            "quiet": True,
            "cookiefile": _get_cookie_path(),
            "no_warnings": True
        }
        with yt_dlp.YoutubeDL(_ydl_opts) as ydl:
            _info = ydl.extract_info(link, download=False)
            return [
                {
                    "format": f["format"],
                    "filesize": f.get("filesize", 0),
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "format_note": f.get("format_note", ""),
                    "yturl": link,
                }
                for f in _info["formats"]
                if not "dash" in str(f.get("format", "")).lower()
            ], link

    async def _get_slider_data(self, link: str, index: int, is_video_id: bool = False):
        if is_video_id:
            link = self._video_base + link
        if "&" in link:
            link = link.split("&")[0]
            
        _results = (await VideosSearch(link, limit=10).next())["result"]
        _item = _results[index]
        return (
            _item["title"],
            _item["duration"],
            _item["thumbnails"][0]["url"].split("?")[0],
            _item["id"]
        )

    def _extract_id(self, url: str) -> str:
        _patterns = [
            r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|v/|watch\?v=))([0-9A-Za-z_-]{11})",
            r"youtube\.com/playlist\?list=([0-9A-Za-z_-]+)"
        ]
        for _p in _patterns:
            _match = re.search(_p, url)
            if _match:
                return _match.group(1)
        return ""

    async def _download_media(
        self,
        link: str,
        is_video: bool = False,
        is_video_id: bool = False,
        is_song: bool = False,
        format_id: str = None,
        title: str = None
    ):
        _loop = asyncio.get_running_loop()
        
        if is_video_id:
            link = self._video_base + link
            
        if is_song:
            _ext = "mp4" if is_video else "mp3"
            _tmpl = f"downloads/{title}.{_ext}" if title else "downloads/%(id)s.%(ext)s"
            
            _opts = {
                "format": f"{format_id}+140" if is_video else format_id,
                "outtmpl": _tmpl,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": _get_cookie_path(),
                "prefer_ffmpeg": True,
            }
            
            if not is_video:
                _opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }]
            else:
                _opts["merge_output_format"] = "mp4"
                
            def _dl():
                with yt_dlp.YoutubeDL(_opts) as ydl:
                    return ydl.download([link])
                    
            await _loop.run_in_executor(None, _dl)
            return f"downloads/{title}.{_ext}", True
            
        else:
            _format = (
                "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])"
                if is_video else "bestaudio/best"
            )
            
            _opts = {
                "format": _format,
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": _get_cookie_path(),
            }
            
            def _dl():
                with yt_dlp.YoutubeDL(_opts) as ydl:
                    _info = ydl.extract_info(link, download=False)
                    _path = f"downloads/{_info['id']}.{_info['ext']}"
                    if not os.path.exists(_path):
                        ydl.download([link])
                    return _path
                    
            _path = await _loop.run_in_executor(None, _dl)
            return _path, True

# Public interface with obfuscated names
YouTubeAPI = _YouTubeHandler
cookie_txt_file = _get_cookie_path
check_file_size = _verify_size
shell_cmd = _run_shell
