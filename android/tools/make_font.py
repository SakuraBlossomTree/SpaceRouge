"""Bake a TrueType font into a CP437 tilesheet PNG that tcod can load.

    python tools/make_font.py                      # builds the default sheets
    python tools/make_font.py FONT.ttf 10 14 out.png

The game loads tilesheets with tcod.tileset.load_tilesheet (16x16 grid,
CP437 order). Text glyphs come from the font; box-drawing lines, solid
blocks and shade characters are drawn by hand so that window frames join
up perfectly whatever the cell size.

Requires Pillow (only for building the sheets, not for playing).
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# CP437 -> Unicode, the same table tcod.tileset.CHARMAP_CP437 uses
_LOW = "\x00☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"


def cp437():
    out = []
    for i in range(256):
        if i < 32:
            out.append(_LOW[i])
        elif i == 127:
            out.append("⌂")
        elif i < 128:
            out.append(chr(i))
        else:
            out.append(bytes([i]).decode("cp437"))
    return out


# (up, down, left, right): 0 = none, 1 = single line, 2 = double line
BOX = {
    "│": (1, 1, 0, 0), "─": (0, 0, 1, 1), "┤": (1, 1, 1, 0), "├": (1, 1, 0, 1),
    "┬": (0, 1, 1, 1), "┴": (1, 0, 1, 1), "┼": (1, 1, 1, 1), "┐": (0, 1, 1, 0),
    "┌": (0, 1, 0, 1), "└": (1, 0, 0, 1), "┘": (1, 0, 1, 0),
    "║": (2, 2, 0, 0), "═": (0, 0, 2, 2), "╣": (2, 2, 2, 0), "╠": (2, 2, 0, 2),
    "╦": (0, 2, 2, 2), "╩": (2, 0, 2, 2), "╬": (2, 2, 2, 2), "╗": (0, 2, 2, 0),
    "╔": (0, 2, 0, 2), "╚": (2, 0, 0, 2), "╝": (2, 0, 2, 0),
    "╡": (1, 1, 2, 0), "╞": (1, 1, 0, 2), "╢": (2, 2, 1, 0), "╟": (2, 2, 0, 1),
    "╖": (0, 2, 1, 0), "╕": (0, 1, 2, 0), "╜": (2, 0, 1, 0), "╛": (1, 0, 2, 0),
    "╓": (0, 2, 0, 1), "╒": (0, 1, 0, 2), "╙": (2, 0, 0, 1), "╘": (1, 0, 0, 2),
    "╤": (0, 1, 2, 2), "╧": (1, 0, 2, 2), "╥": (0, 2, 1, 1), "╨": (2, 0, 1, 1),
    "╪": (1, 1, 2, 2), "╫": (2, 2, 1, 1),
}


def draw_box(d, w, h, arms, thick):
    up, down, left, right = arms
    cx, cy = (w - 1) // 2, (h - 1) // 2
    g = max(1, round(min(w, h) / 6))   # half-gap between double lines

    def hl(y, x0, x1):
        x0, x1 = sorted((x0, x1))
        d.rectangle([x0, y, x1, y + thick - 1], fill=255)

    def vl(x, y0, y1):
        y0, y1 = sorted((y0, y1))
        d.rectangle([x, y0, x + thick - 1, y1], fill=255)

    vert2 = up == 2 or down == 2
    horz2 = left == 2 or right == 2

    # horizontal arms
    for side, weight in (("r", right), ("l", left)):
        if not weight:
            continue
        edge = w - 1 if side == "r" else 0
        sgn = 1 if side == "r" else -1
        if weight == 1:
            end = cx + sgn * g if vert2 else cx
            hl(cy, edge, end)
        else:
            top_end = cx + sgn * g if up == 2 else (cx - sgn * g if down == 2 else cx)
            bot_end = cx + sgn * g if down == 2 else (cx - sgn * g if up == 2 else cx)
            hl(cy - g, edge, top_end)
            hl(cy + g, edge, bot_end)

    # vertical arms
    for side, weight in (("d", down), ("u", up)):
        if not weight:
            continue
        edge = h - 1 if side == "d" else 0
        sgn = 1 if side == "d" else -1
        if weight == 1:
            end = cy + sgn * g if horz2 else cy
            vl(cx, edge, end)
        else:
            l_end = cy + sgn * g if left == 2 else (cy - sgn * g if right == 2 else cy)
            r_end = cy + sgn * g if right == 2 else (cy - sgn * g if left == 2 else cy)
            vl(cx - g, edge, l_end)
            vl(cx + g, edge, r_end)


def draw_special(ch, d, w, h, thick):
    if ch in BOX:
        draw_box(d, w, h, BOX[ch], thick)
        return True
    full = [0, 0, w - 1, h - 1]
    if ch == "█":
        d.rectangle(full, fill=255)
    elif ch == "▄":
        d.rectangle([0, h // 2, w - 1, h - 1], fill=255)
    elif ch == "▀":
        d.rectangle([0, 0, w - 1, h // 2 - 1], fill=255)
    elif ch == "▌":
        d.rectangle([0, 0, w // 2 - 1, h - 1], fill=255)
    elif ch == "▐":
        d.rectangle([w // 2, 0, w - 1, h - 1], fill=255)
    elif ch in "░▒▓":
        # flat tints read better than dither patterns at small sizes
        d.rectangle(full, fill={"░": 70, "▒": 130, "▓": 195}[ch])
    else:
        return False
    return True


def build(ttf, w, h, out, size=None):
    if size is None:
        # largest pixel size whose advance width still fits the cell
        size = 6
        while True:
            f = ImageFont.truetype(ttf, size + 1)
            asc, desc = f.getmetrics()
            if f.getlength("M") > w or (asc + desc) > h + 3:
                break
            size += 1
    font = ImageFont.truetype(ttf, size)
    asc, desc = font.getmetrics()
    # vertically centre the cap-height + descender band in the cell
    _, cap_top, _, _ = font.getbbox("H", anchor="ls")
    _, _, _, desc_bot = font.getbbox("gjpqy", anchor="ls")
    band = desc_bot - cap_top
    baseline = (h - band) // 2 - cap_top
    thick = 1 if h < 20 else 2

    sheet = Image.new("L", (w * 16, h * 16), 0)
    for i, ch in enumerate(cp437()):
        if ord(ch) in (0, 32):
            continue
        cell = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(cell)
        if not draw_special(ch, d, w, h, thick):
            adv = font.getlength(ch)
            x = (w - adv) / 2
            d.text((x, baseline), ch, font=font, fill=255, anchor="ls")
        sheet.paste(cell, ((i % 16) * w, (i // 16) * h))

    rgba = Image.new("RGBA", sheet.size, (255, 255, 255, 0))
    rgba.putalpha(sheet)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    rgba.save(out)
    print(f"{out}: {w}x{h} cells, font size {size}px")


DEFAULTS = [
    ("assets/fonts/DejaVuSansMono.ttf", 10, 14, "assets/fonts/sans_10x14.png"),
    ("assets/fonts/DejaVuSansMono.ttf", 12, 17, "assets/fonts/sans_12x17.png"),
    ("assets/fonts/DejaVuSansMono.ttf", 8, 12, "assets/fonts/sans_8x12.png"),
]

if __name__ == "__main__":
    if len(sys.argv) == 5:
        ttf, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        build(ttf, w, h, out)
    else:
        for ttf, w, h, out in DEFAULTS:
            build(ttf, w, h, out)
