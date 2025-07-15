import os
import re
import textwrap

import aiofiles
import aiohttp
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps
)
from youtubesearchpython.__future__ import VideosSearch

from config import YOUTUBE_IMG_URL


def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    ratio = min(widthRatio, heightRatio)
    newWidth = int(image.size[0] * ratio)
    newHeight = int(image.size[1] * ratio)
    image = image.resize((newWidth, newHeight), Image.ANTIALIAS)
    return image


async def get_thumb(videoid):
    final_path = f"cache/{videoid}.png"
    if os.path.isfile(final_path):
        return final_path

    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        results = VideosSearch(url, limit=1)
        result_data = await results.next()
        if not result_data["result"]:
            raise Exception("No results found")

        result = result_data["result"][0]
        title = re.sub(r"\W+", " ", result.get("title", "Unknown Title")).title()
        duration = result.get("duration", "Unknown Duration")
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        views = result.get("viewCount", {}).get("short", "Unknown Views")
        channel = result.get("channel", {}).get("name", "Unknown Channel")

        # Download thumbnail
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    fpath = f"cache/thumb{videoid}.png"
                    async with aiofiles.open(fpath, mode="wb") as f:
                        await f.write(await resp.read())

        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube.copy())
        center_thumb = changeImageSize(940, 420, youtube.copy())

        # Rounded center image mask
        mask = Image.new("L", center_thumb.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle(
            [0, 0, center_thumb.size[0], center_thumb.size[1]],
            radius=40,
            fill=255
        )

        # Background blur (softer)
        image2 = image1.convert("RGBA")
        background = image2.filter(ImageFilter.BoxBlur(15))
        background = ImageEnhance.Brightness(background).enhance(0.8)

        # Paste rounded thumbnail
        thumb_pos = (170, 90)
        center_thumb_rgba = center_thumb.convert("RGBA")
        background.paste(center_thumb_rgba, thumb_pos, mask)

        # Draw text
        draw = ImageDraw.Draw(background)
        font = ImageFont.truetype("Opus/assets/font2.ttf", 30)
        font2 = ImageFont.truetype("Opus/assets/font2.ttf", 30)
        arial = ImageFont.truetype("Opus/assets/font2.ttf", 30)

        # Channel | Views
        draw.text((50, 565), f"{channel} | {views[:23]}", fill="white", font=arial)

        # Title
        draw.text((50, 600), title, fill="white", font=font, stroke_fill="white")

        # Start and End Time
        draw.text((50, 640), "00:25", fill="white", font=font2, stroke_width=1, stroke_fill="white")
        draw.text((1150, 640), duration[:23], fill="white", font=font2, stroke_width=1, stroke_fill="white")

        draw.line((150, 660, 1130, 660), width=6, fill="white")

        # Recreation Music text at right side of center thumbnail
        rec_font = ImageFont.truetype("Opus/assets/font.ttf", 45)
        rec_text = "Recreation Music"
        rec_text_w, rec_text_h = draw.textsize(rec_text, font=rec_font)
        rec_x = thumb_pos[0] + center_thumb.width + 50  # 50px gap after thumbnail
        rec_y = thumb_pos[1] + (center_thumb.height // 2) - (rec_text_h // 2)
        draw.text((rec_x, rec_y), rec_text, fill="white", font=rec_font)

        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        background.save(final_path)
        return final_path

    except Exception as e:
        print("Thumbnail generation error:", e)
        return YOUTUBE_IMG_URL
