"""
utils/image_fit.py — Fit an image into a specific region of an asset
─────────────────────────────────────────────────────────────────────
Uses perspective transform to warp the source image into a polygon
region defined by 4 corner points on the asset.
"""

from PIL import Image
import numpy as np
import aiohttp
import io


async def fetch_image(url: str) -> Image.Image:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
    return Image.open(io.BytesIO(data)).convert("RGBA")


def perspective_transform(src: Image.Image, dst_points: list, dst_size: tuple) -> Image.Image:
    """
    Warp src image to fill the quadrilateral defined by dst_points.

    dst_points: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                 top-left, top-right, bottom-right, bottom-left
    dst_size:   (width, height) of the destination canvas
    """
    w, h = src.size

    src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_pts = np.float32(dst_points)

    def compute_homography(src_pts, dst_pts):
        A = []
        for (xs, ys), (xd, yd) in zip(src_pts, dst_pts):
            A.append([-xs, -ys, -1,  0,   0,  0, xd*xs, xd*ys, xd])
            A.append([ 0,   0,  0, -xs, -ys, -1, yd*xs, yd*ys, yd])
        A = np.array(A)
        _, _, Vt = np.linalg.svd(A)
        H = Vt[-1].reshape(3, 3)
        return H / H[2, 2]

    H = compute_homography(dst_pts, src_pts)  # dst -> src (inverse mapping)

    dw, dh = dst_size
    src_arr = np.array(src.convert("RGBA"))

    ys, xs = np.mgrid[0:dh, 0:dw].astype(np.float32)
    ones   = np.ones_like(xs)
    coords = np.stack([xs, ys, ones], axis=-1).reshape(-1, 3)

    mapped = (H @ coords.T).T
    mapped /= mapped[:, 2:3]
    sx = mapped[:, 0].reshape(dh, dw)
    sy = mapped[:, 1].reshape(dh, dw)

    def point_in_quad(px, py, pts):
        def cross(ax, ay, bx, by): return ax * by - ay * bx
        n = len(pts)
        inside = np.ones(px.shape, dtype=bool)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            c = cross(x2 - x1, y2 - y1, px - x1, py - y1)
            inside &= (c >= 0)
        return inside

    mask = point_in_quad(xs, ys, dst_pts)
    sx_c = np.clip(sx, 0, w - 1).astype(np.int32)
    sy_c = np.clip(sy, 0, h - 1).astype(np.int32)

    out = np.zeros((dh, dw, 4), dtype=np.uint8)
    out[mask] = src_arr[sy_c[mask], sx_c[mask]]

    return Image.fromarray(out, "RGBA")


def fit_image(base: Image.Image, asset_path: str, region: list,
              layer: str = "behind") -> tuple[io.BytesIO, str]:
    """
    Fits the base image into the region of the asset.

    Parameters
    ----------
    base        : PIL Image — the user's image to fit in
    asset_path  : str       — path to the asset PNG with the region
    region      : list      — 4 [x, y] points (top-left, top-right, bottom-right, bottom-left)
    layer       : str       — "behind" (default): target under asset, visible through
                              transparent parts.
                              "infront": target on top of asset.

    Returns
    -------
    (io.BytesIO, str) — image buffer and file extension
    """
    asset  = Image.open(asset_path).convert("RGBA")
    warped = perspective_transform(base.convert("RGBA"), region, asset.size)
    result = Image.new("RGBA", asset.size, (0, 0, 0, 0))

    if layer == "infront":
        result = Image.alpha_composite(result, asset)
        result = Image.alpha_composite(result, warped)
    else:
        # "behind" — warped under asset (default)
        result = Image.alpha_composite(result, warped)
        result = Image.alpha_composite(result, asset)

    buf = io.BytesIO()
    result.convert("RGB").save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf, "jpg"


def find_image_in_message(message) -> str | None:
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
