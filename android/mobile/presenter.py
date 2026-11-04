"""Draws a tcod-style Console onto a pygame surface using a glyph atlas.

* The console fills the whole screen at about 46 rows: the biggest font
  sheet that fits is used (a 1080p phone gets 16x23 cells, ~150 x 46), and
  big screens are scaled up so text stays large.
* Redraws only the cells that changed since the last frame, so animated
  stars cost a few dozen blits instead of 7,440.
* Coloured glyphs are cached (colours quantised so twinkling stars don't
  flood the cache).
"""

import os
from pathlib import Path

import numpy as np
import pygame

# CP437 -> Unicode (same table as tcod.tileset.CHARMAP_CP437)
_LOW = "\x00☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"


def _cp437_index():
    table = {}
    for i in range(256):
        if i < 32:
            c = _LOW[i]
        elif i == 127:
            c = "⌂"
        elif i < 128:
            c = chr(i)
        else:
            c = bytes([i]).decode("cp437")
        table[ord(c)] = i
    return table


CP437 = _cp437_index()
QUESTION = ord("?")

SHEETS = {
    "sans": ["assets/fonts/sans_8x12.png", "assets/fonts/sans_10x14.png",
             "assets/fonts/sans_12x17.png", "assets/fonts/sans_14x20.png",
             "assets/fonts/sans_16x23.png"],
    "classic": ["assets/fonts/classic_12x12.png"],
}


TARGET_ROWS = 46      # rows on screen: ~23 px per row on a 1080p phone
MIN_ROWS = 40         # the Exchange / Handbook windows need about this many


class Presenter:
    """Draws the console full-screen. The console size (cols x rows) is
    chosen to suit the screen, so the game fills it edge to edge."""

    def __init__(self, family="sans"):
        self.family = family
        self.sheet_path = None
        self.cols = self.rows = 0
        self.canvas = None
        self.prev = None
        self.dest = pygame.Rect(0, 0, 0, 0)
        self._scaled = None
        self._dirty = True
        self._dirty_rects = []
        self._sizes = {}

    # ---- fonts -----------------------------------------------------------

    def _sheet_size(self, path):
        # (absolute paths: on Android SDL resolves relative ones inside the APK)
        if path not in self._sizes:
            img = pygame.image.load(os.path.abspath(path))
            self._sizes[path] = (img.get_width() // 16, img.get_height() // 16)
        return self._sizes[path]

    def _sheets(self):
        paths = [p for p in SHEETS.get(self.family, SHEETS["sans"]) if Path(p).exists()]
        if not paths:
            paths = [p for fam in SHEETS.values() for p in fam if Path(p).exists()]
        return sorted(paths, key=lambda p: self._sheet_size(p)[1])

    def plan(self, area_w, area_h):
        """Pick (sheet, cols, rows, scale) for a screen of area_w x area_h px."""
        sheets = self._sheets()
        best = sheets[0]
        for p in sheets:
            if self._sheet_size(p)[1] * TARGET_ROWS <= area_h:
                best = p
        tw, th = self._sheet_size(best)
        # always ~46 rows: extra screen height makes the text bigger, not smaller
        rows = TARGET_ROWS if area_h // th >= TARGET_ROWS else max(MIN_ROWS, area_h // th)
        scale = area_h / (rows * th)
        if 0.97 < scale < 1.0 or 1.0 < scale < 1.03:
            scale = 1.0
        cols = int(area_w / (tw * scale))
        return best, cols, rows, scale

    def _load_atlas(self, path, cell=None):
        """Load a sheet; if cell=(w, h) differs from the sheet, resize it ONCE
        here so frames never need scaling (scaling a whole frame is slow)."""
        sheet = pygame.image.load(os.path.abspath(path)).convert_alpha()
        sw, sh = sheet.get_width() // 16, sheet.get_height() // 16
        if cell and cell != (sw, sh):
            scaler = pygame.transform.scale if self.family == "classic" else pygame.transform.smoothscale
            sheet = scaler(sheet, (cell[0] * 16, cell[1] * 16))
        self.tw, self.th = sheet.get_width() // 16, sheet.get_height() // 16
        self.glyphs = []
        for i in range(256):
            rect = pygame.Rect((i % 16) * self.tw, (i // 16) * self.th, self.tw, self.th)
            self.glyphs.append(sheet.subsurface(rect).copy())
        self.cache = {}

    def layout(self, area):
        """Fit to the screen area. Returns (cols, rows) of the console to use.

        The glyphs are resized once to the exact cell size, so the canvas is
        drawn 1:1 every frame - no per-frame scaling."""
        path, cols, rows, scale = self.plan(area.width, area.height)
        sw, sh = self._sheet_size(path)
        ch = sh if scale == 1.0 else max(6, area.height // rows)
        cw = sw if scale == 1.0 else max(4, round(sw * ch / sh))
        cols = max(20, area.width // cw)
        if (path, (cw, ch)) != (self.sheet_path, getattr(self, "_cell", None)):
            self._load_atlas(path, (cw, ch))
            self._cell = (cw, ch)
            self.sheet_path = path
        if self.canvas is None or self.canvas.get_size() != (cols * cw, rows * ch):
            self.canvas = pygame.Surface((cols * cw, rows * ch)).convert()
        self.cols, self.rows = cols, rows
        self.prev = None
        self._dirty_rects = []
        self.dest = pygame.Rect(area.x + (area.width - cols * cw) // 2,
                                area.y + (area.height - rows * ch) // 2,
                                cols * cw, rows * ch)
        self._dirty = True
        return cols, rows

    def set_family(self, family, area):
        self.family = family
        self.sheet_path = None
        self._cell = None
        return self.layout(area)

    # ---- drawing ------------------------------------------------------------

    def _glyph(self, idx, fg, bg):
        """A ready-made OPAQUE cell: the glyph tinted and already blended onto
        its background colour. Copying an opaque surface is a plain memory
        copy; blitting a see-through glyph means per-pixel alpha blending,
        which pygame only speeds up on PC chips (SSE/AVX), not phone ARM chips."""
        key = (idx, fg[0] >> 3, fg[1] >> 3, fg[2] >> 3, int(bg[0]), int(bg[1]), int(bg[2]))
        g = self.cache.get(key)
        if g is None:
            if len(self.cache) > 6000:
                self.cache.clear()
            tinted = self.glyphs[idx].copy()
            tinted.fill((int(fg[0]), int(fg[1]), int(fg[2]), 255),
                        special_flags=pygame.BLEND_RGBA_MULT)
            g = pygame.Surface((self.tw, self.th)).convert()
            g.fill((int(bg[0]), int(bg[1]), int(bg[2])))
            g.blit(tinted, (0, 0))
            self.cache[key] = g
        return g

    def render(self, console):
        """Update the canvas from the console (changed cells only)."""
        rgb = console.rgb
        if self.prev is None or self.prev.shape != rgb.shape:
            changed = np.ones(rgb.shape, dtype=bool)
        else:
            p = self.prev
            changed = ((rgb["ch"] != p["ch"])
                       | (rgb["fg"] != p["fg"]).any(axis=-1)
                       | (rgb["bg"] != p["bg"]).any(axis=-1))
        ys, xs = np.nonzero(changed)
        if len(ys) == 0:
            return False
        tw, th = self.tw, self.th
        canvas = self.canvas
        chs, fgs, bgs = rgb["ch"], rgb["fg"], rgb["bg"]
        fill, blit, glyph, cp = canvas.fill, canvas.blit, self._glyph, CP437.get
        for y, x in zip(ys.tolist(), xs.tolist()):
            px, py = x * tw, y * th
            bg = bgs[y, x]
            code = int(chs[y, x])
            if code in (0, 32):
                fill((int(bg[0]), int(bg[1]), int(bg[2])), (px, py, tw, th))
            else:
                blit(glyph(cp(code, QUESTION), fgs[y, x], bg), (px, py))

        # Changed screen areas: one rectangle per run of neighbouring changed
        # cells in a row (two twinkling stars at opposite ends of a row are
        # two small rects, not one full-width strip).
        pad = np.zeros((changed.shape[0], changed.shape[1] + 2), dtype=np.int8)
        pad[:, 1:-1] = changed
        d = np.diff(pad, axis=1)
        sy, sx = np.nonzero(d == 1)
        _, ex = np.nonzero(d == -1)
        for y, x0, x1 in zip(sy.tolist(), sx.tolist(), ex.tolist()):
            self._dirty_rects.append(pygame.Rect(x0 * tw, y * th, (x1 - x0) * tw, th))

        self.prev = rgb.copy()
        self._dirty = True
        return True

    def present(self, screen):
        """Copy only changed cells to the screen. Returns updated screen rects."""
        if not self._dirty_rects:
            return []
        dx, dy = self.dest.topleft
        screen_rects = []
        for rect in self._dirty_rects:
            screen.blit(self.canvas, (dx + rect.x, dy + rect.y), area=rect)
            screen_rects.append(rect.move(dx, dy))
        self._dirty_rects.clear()
        self._dirty = False
        return screen_rects

    def present_all(self, screen):
        """Copy the whole canvas (after a resize / font change)."""
        screen.blit(self.canvas, self.dest.topleft)
        self._dirty_rects.clear()
        self._dirty = False

    def cell_at(self, pos):
        """Screen position -> console cell (or None)."""
        if not self.dest.collidepoint(pos):
            return None
        x = (pos[0] - self.dest.x) * self.cols // max(1, self.dest.width)
        y = (pos[1] - self.dest.y) * self.rows // max(1, self.dest.height)
        return int(x), int(y)
