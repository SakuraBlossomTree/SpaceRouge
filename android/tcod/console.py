"""tcod-compatible character console backed by numpy.

rgb is a structured (height, width) array with "ch", "fg" and "bg" fields,
indexed [y, x] like tcod's default C order.
"""

import numpy as np

RGB = np.dtype([("ch", np.int32), ("fg", "3u1"), ("bg", "3u1")])


class Console:
    def __init__(self, width, height, order="C"):
        self.width = width
        self.height = height
        self.rgb = np.zeros((height, width), dtype=RGB)
        self.clear()

    @property
    def ch(self):
        return self.rgb["ch"]

    @property
    def fg(self):
        return self.rgb["fg"]

    @property
    def bg(self):
        return self.rgb["bg"]

    def clear(self, ch=0x20, fg=(255, 255, 255), bg=(0, 0, 0)):
        self.rgb["ch"] = ch
        self.rgb["fg"] = fg
        self.rgb["bg"] = bg

    def _put(self, x, y, c, fg, bg):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.rgb["ch"][y, x] = ord(c)
            if fg is not None:
                self.rgb["fg"][y, x] = fg
            if bg is not None:
                self.rgb["bg"][y, x] = bg

    def print(self, x, y, text, fg=None, bg=None, bg_blend=None, alignment=0, **kwargs):
        # whole-line slice writes (one numpy op per line, not per character)
        text = str(text)
        ch_a, fg_a, bg_a = self.rgb["ch"], self.rgb["fg"], self.rgb["bg"]
        for dy, line in enumerate(text.split("\n")):
            sx = x
            if alignment == 2:
                sx = x - len(line) // 2
            elif alignment == 1:
                sx = x - len(line) + 1
            yy = y + dy
            if not (0 <= yy < self.height) or not line:
                continue
            a, b = max(0, sx), min(self.width, sx + len(line))
            if a >= b:
                continue
            seg = line[a - sx:b - sx]
            if len(seg) == 1:
                ch_a[yy, a] = ord(seg)
            else:
                ch_a[yy, a:b] = [ord(c) for c in seg]
            if fg is not None:
                fg_a[yy, a:b] = fg
            if bg is not None:
                bg_a[yy, a:b] = bg

    def draw_rect(self, x, y, width, height, ch, fg=None, bg=None, bg_blend=None):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + width), min(self.height, y + height)
        if x0 >= x1 or y0 >= y1:
            return
        region = self.rgb[y0:y1, x0:x1]
        if ch:
            region["ch"] = ch
        if fg is not None:
            region["fg"] = fg
        if bg is not None:
            region["bg"] = bg

    def draw_frame(self, x, y, width, height, title="", clear=True, fg=None, bg=None,
                   bg_blend=None, *, decoration="┌─┐│ │└─┘"):
        d = decoration
        if clear:
            self.draw_rect(x + 1, y + 1, width - 2, height - 2, 0x20, fg, bg)
        for xx in range(x + 1, x + width - 1):
            self._put(xx, y, d[1], fg, bg)
            self._put(xx, y + height - 1, d[7], fg, bg)
        for yy in range(y + 1, y + height - 1):
            self._put(x, yy, d[3], fg, bg)
            self._put(x + width - 1, yy, d[5], fg, bg)
        self._put(x, y, d[0], fg, bg)
        self._put(x + width - 1, y, d[2], fg, bg)
        self._put(x, y + height - 1, d[6], fg, bg)
        self._put(x + width - 1, y + height - 1, d[8], fg, bg)

    def blit(self, dest, dest_x=0, dest_y=0, src_x=0, src_y=0, width=0, height=0,
             fg_alpha=1.0, bg_alpha=1.0, key_color=None):
        w = width or self.width
        h = height or self.height
        w = min(w, dest.width - dest_x, self.width - src_x)
        h = min(h, dest.height - dest_y, self.height - src_y)
        if w <= 0 or h <= 0:
            return
        dest.rgb[dest_y:dest_y + h, dest_x:dest_x + w] = self.rgb[src_y:src_y + h, src_x:src_x + w]
