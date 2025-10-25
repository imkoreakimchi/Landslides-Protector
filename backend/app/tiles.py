from __future__ import annotations

from io import BytesIO
from typing import Tuple

from PIL import Image, ImageDraw


COLOR_SCHEMES = {
    "hazard": (211, 47, 47, 90),
    "rain": (33, 150, 243, 100),
    "burn": (255, 109, 0, 80),
}


def _tile_canvas(color: Tuple[int, int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (255, 255)], fill=color)
    return img


def render_tile(layer: str) -> bytes:
    color = COLOR_SCHEMES.get(layer)
    if not color:
        color = (120, 120, 120, 60)
    img = _tile_canvas(color)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()
