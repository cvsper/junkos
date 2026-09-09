"""Generate the Call Desk PWA icons from the brand logo.

    python scripts/make_desk_icons.py            (from backend/)

Writes static/icon-192.png and static/icon-512.png: the U-truck logo centred
on the desk's #0B0E12 ground inside the maskable safe zone (80%), so the icon
survives Android's circle/squircle masks and looks right on an iOS home
screen. Pillow only.
"""
from __future__ import annotations

import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(os.path.dirname(HERE), "static")
SRC = os.path.join(STATIC, "brand-logo.png")
BG = (0x0B, 0x0E, 0x12, 255)
SAFE = 0.66          # logo footprint as a fraction of the canvas (inside the 80% maskable zone)


def make_icon(size, out_path, src=SRC):
    logo = Image.open(src).convert("RGBA")
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    target = int(size * SAFE)
    w, h = logo.size
    scale = min(target / w, target / h)
    logo = logo.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), BG)
    x = (size - logo.width) // 2
    y = (size - logo.height) // 2
    canvas.alpha_composite(logo, (x, y))
    canvas.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


def main(argv=None):
    for size in (192, 512):
        out = os.path.join(STATIC, "icon-{}.png".format(size))
        make_icon(size, out)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
