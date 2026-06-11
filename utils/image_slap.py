"""
utils/image_slap.py — Reusable "slap an image on top of another image" utility
───────────────────────────────────────────────────────────────────────────────
Supports static images (PNG, JPG, WEBP) and animated GIFs.
"""

from PIL import Image
import aiohttp
import io
import random


async def fetch_image(url: str) -> Image.Image:
    """Download an image from a URL and return a PIL Image."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
    return Image.open(io.BytesIO(data))


def _build_asset(asset_path: str, short_side: int,
                 scale_min: float, scale_max: float,
                 rotate_min: float, rotate_max: float):
    """Scale and rotate the asset once, reuse across all frames."""
    asset_raw = Image.open(asset_path).convert("RGBA")
    size  = int(short_side * random.uniform(scale_min, scale_max))
    asset = asset_raw.resize((size, size), Image.LANCZOS)
    angle = random.uniform(rotate_min, rotate_max)
    asset = asset.rotate(angle, expand=True, resample=Image.BICUBIC)
    return asset


def _random_pos(base_w, base_h, asset_w, asset_h):
    """Pick a random position, allowing partial overflow off edges."""
    x = random.randint(-asset_w // 3, base_w - asset_w * 2 // 3)
    y = random.randint(-asset_h // 3, base_h - asset_h * 2 // 3)
    return x, y


def slap_image(base: Image.Image, asset_path: str,
               scale_min=0.35, scale_max=0.65,
               rotate_min=-45, rotate_max=45) -> tuple[io.BytesIO, str]:
    """
    Slaps an asset image onto the base image.
    Handles both static images and animated GIFs.

    Returns
    -------
    (io.BytesIO, str) — image buffer and file extension ("jpg" or "gif")
    """
    short_side = min(base.width, base.height)
    asset = _build_asset(asset_path, short_side, scale_min, scale_max, rotate_min, rotate_max)
    x, y  = _random_pos(base.width, base.height, asset.width, asset.height)

    # ── Animated GIF ──────────────────────────────────────────────────────────
    if getattr(base, "is_animated", False) or getattr(base, "n_frames", 1) > 1:
        frames = []
        durations = []

        for i in range(base.n_frames):
            base.seek(i)
            frame = base.convert("RGBA").copy()
            frame.paste(asset, (x, y), asset)
            frames.append(frame.convert("RGBA"))
            durations.append(base.info.get("duration", 50))

        buf = io.BytesIO()
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            loop=0,
            duration=durations,
            disposal=2,
        )
        buf.seek(0)
        return buf, "gif"

    # ── Static image ──────────────────────────────────────────────────────────
    result = base.convert("RGBA").copy()
    result.paste(asset, (x, y), asset)

    buf = io.BytesIO()
    result.convert("RGB").save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf, "jpg"


def find_image_in_message(message) -> str | None:
    """Return the first image URL found in a message's attachments or embeds."""
    for att in message.attachments:
        if att.content_type and (
            att.content_type.startswith("image") or att.filename.endswith(".gif")
        ):
            return att.url
    for embed in message.embeds:
        if embed.image and embed.image.url:
            return embed.image.url
        if embed.thumbnail and embed.thumbnail.url:
            return embed.thumbnail.url
    return None
