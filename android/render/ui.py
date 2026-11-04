"""Shared TUI toolkit: screen layout, colour palette and drawing helpers.

Every screen draws through these helpers so the whole game shares one
look: double-line frames, coloured bars, key-hint rows and highlighted
menu rows.

Layout (in cells):

    +--------------------- 82 ---------------------++------ 38 ------+
    |  MAP VIEWPORT  (80 x 60 interior)            ||  SIDEBAR       |
    |  galaxy / system / combat / hyperspace and   ||  ship, loan,   |
    |  all menu windows are drawn in here          ||  location,     |
    |                                              ||  missions, log |
    +----------------------------------------------++----------------+

The map viewport is its own 80x60 console (the same size the world is
generated for), so world coordinates never need translating.
"""

import textwrap

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

MAP_W, MAP_H = 80, 60            # interior of the viewport == world size
SIDE_W = 38

SCREEN_W = MAP_W + 2 + SIDE_W    # 120
SCREEN_H = MAP_H + 2             # 62

MAP_X, MAP_Y = 1, 1              # where the map console is blitted
SIDE_X = MAP_W + 2               # 82

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG = (6, 8, 16)
PANEL_BG = (10, 14, 26)
BORDER = (52, 74, 112)
BORDER_HI = (90, 150, 210)
TITLE = (120, 205, 255)
TEXT = (205, 210, 220)
DIM = (105, 112, 135)
FAINT = (55, 60, 80)
KEY = (255, 205, 90)
ACCENT = (90, 210, 220)
GOOD = (95, 220, 125)
WARN = (240, 195, 70)
BAD = (240, 85, 85)
SEL_BG = (28, 52, 88)
SEL_FG = (255, 255, 255)
PLAYER = (255, 235, 120)

DOUBLE = "╔═╗║ ║╚═╝"
SINGLE = "┌─┐│ │└─┘"


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def fmt_int(n):
    """1234567 -> '1,234,567'."""
    return f"{int(round(n)):,}"


def clip(text, width):
    """Trim text to width, adding an ellipsis when cut."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return text[:1]
    return text[: width - 1] + "."


def wrap(text, width):
    lines = []
    for para in str(text).split("\n"):
        if not para.strip():
            lines.append("")
        else:
            lines.extend(textwrap.wrap(para, width=width))
    return lines


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale_color(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def vivid(c):
    """Lift very dark / saturated colours (pure blue etc.) so they read on black."""
    lum = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    if lum >= 140:
        return tuple(c)
    return lerp_color(c, (255, 255, 255), min(0.4, (140 - lum) / 255 * 1.4))


def dim_console(console, factor=0.3):
    """Darken everything already drawn (used behind modal windows)."""
    console.rgb["fg"] = (console.rgb["fg"] * factor).astype("u1")
    console.rgb["bg"] = (console.rgb["bg"] * factor).astype("u1")


def fill(console, x, y, w, h, bg=PANEL_BG):
    console.draw_rect(x, y, w, h, ord(" "), fg=TEXT, bg=bg)


# ---------------------------------------------------------------------------
# Frames & panels
# ---------------------------------------------------------------------------

def frame(console, x, y, w, h, title="", *, fg=BORDER, bg=PANEL_BG,
          title_fg=TITLE, double=True, clear=True, right_title=""):
    """Draw a box with an optional title set into the top border."""
    console.draw_frame(
        x, y, w, h, clear=clear, fg=fg, bg=bg,
        decoration=DOUBLE if double else SINGLE,
    )
    left, right = ("╡", "╞") if double else ("┤", "├")
    if title:
        t = clip(title.upper(), w - 6)
        console.print(x + 2, y, left, fg=fg, bg=bg)
        console.print(x + 3, y, f" {t} ", fg=title_fg, bg=bg)
        console.print(x + 5 + len(t), y, right, fg=fg, bg=bg)
    if right_title:
        t = clip(right_title, w - 8)
        rx = x + w - len(t) - 5
        console.print(rx, y, left, fg=fg, bg=bg)
        console.print(rx + 1, y, f" {t} ", fg=DIM, bg=bg)
        console.print(rx + 3 + len(t), y, right, fg=fg, bg=bg)


def hline(console, x, y, w, fg=BORDER, bg=PANEL_BG, double=True, join=True):
    """Horizontal divider; with join=True it tees into a surrounding frame."""
    if double:
        mid, l, r = "═", "╠", "╣"
    else:
        mid, l, r = "─", "├", "┤"
    console.print(x, y, mid * w, fg=fg, bg=bg)
    if join:
        console.print(x, y, l, fg=fg, bg=bg)
        console.print(x + w - 1, y, r, fg=fg, bg=bg)


def window(console, w, h, title="", *, area_w=None, area_h=None,
           y=None, fg=BORDER_HI, right_title=""):
    """Centered modal window inside the map viewport. Returns (x, y)."""
    area_w = MAP_W if area_w is None else area_w
    area_h = MAP_H if area_h is None else area_h
    x = (area_w - w) // 2
    if y is None:
        y = (area_h - h) // 2
    # drop shadow
    console.draw_rect(x + 1, y + 1, w, h, ord(" "), bg=(0, 0, 0))
    frame(console, x, y, w, h, title, fg=fg, right_title=right_title)
    return x, y


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def text(console, x, y, s, fg=TEXT, bg=None):
    console.print(x, y, s, fg=fg, bg=bg)


def center(console, cx, y, s, fg=TEXT, bg=None):
    console.print(cx - len(s) // 2, y, s, fg=fg, bg=bg)


def right(console, rx, y, s, fg=TEXT, bg=None):
    """Right-align so the last character sits at column rx."""
    console.print(rx - len(s) + 1, y, s, fg=fg, bg=bg)


def kv(console, x, y, w, label, value, *, label_fg=DIM, value_fg=TEXT, bg=None):
    """'Label ........ value' row, value right-aligned to width w."""
    console.print(x, y, label, fg=label_fg, bg=bg)
    value = clip(str(value), max(1, w - len(label) - 1))
    console.print(x + w - len(value), y, value, fg=value_fg, bg=bg)


def paragraph(console, x, y, w, s, fg=TEXT, max_lines=None, bg=None):
    """Word-wrapped text. Returns number of lines used."""
    lines = wrap(s, w)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = clip(lines[-1] + " ...", w)
    for i, line in enumerate(lines):
        console.print(x, y + i, line, fg=fg, bg=bg)
    return len(lines)


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------

def ratio_color(ratio, invert=False):
    """Green when healthy, amber when low, red when critical."""
    if invert:
        ratio = 1 - ratio
    if ratio > 0.5:
        return GOOD
    if ratio > 0.25:
        return WARN
    return BAD


def bar(console, x, y, w, value, maximum, fg=None, *, empty_fg=FAINT, bg=None,
        invert=False):
    """Solid gauge bar. Colour follows the fill ratio unless fg is given."""
    ratio = 0.0 if not maximum else max(0.0, min(1.0, value / maximum))
    filled = int(round(ratio * w))
    if value > 0 and filled == 0:
        filled = 1
    color = fg or ratio_color(ratio, invert)
    console.print(x, y, "█" * filled, fg=color, bg=bg)
    console.print(x + filled, y, "░" * (w - filled), fg=empty_fg, bg=bg)
    return color


def meter(console, x, y, label, value, maximum, w, *, fmt="{:.0f}/{:.0f}",
          fg=None, invert=False, bg=None):
    """Two-line gauge: 'LABEL       12/100' above a full-width bar."""
    color = fg or ratio_color(0 if not maximum else value / maximum, invert)
    console.print(x, y, label, fg=DIM, bg=bg)
    v = fmt.format(value, maximum)
    console.print(x + w - len(v), y, v, fg=color, bg=bg)
    bar(console, x, y + 1, w, value, maximum, color, bg=bg)


# ---------------------------------------------------------------------------
# Menus & key hints
# ---------------------------------------------------------------------------

def key_hint(console, x, y, key, label, *, bg=None, label_fg=DIM):
    """Draws '[KEY] label' and returns the x after it."""
    console.print(x, y, "[", fg=FAINT, bg=bg)
    console.print(x + 1, y, key, fg=KEY, bg=bg)
    console.print(x + 1 + len(key), y, "]", fg=FAINT, bg=bg)
    console.print(x + 3 + len(key), y, label, fg=label_fg, bg=bg)
    return x + 3 + len(key) + len(label) + 2


def hint_row(console, x, y, hints, *, bg=None, max_w=None):
    """A row of key hints. Wraps onto the next line if max_w is given."""
    cx, cy = x, y
    for key, label in hints:
        need = len(key) + len(label) + 3
        if max_w is not None and cx > x and cx + need > x + max_w:
            cx, cy = x, cy + 1
        cx = key_hint(console, cx, cy, key, label, bg=bg)
    return cy - y + 1


def hint_row_centered(console, cx, y, hints, *, bg=PANEL_BG):
    """Centered hint row; clears a strip behind it so it can sit on a border."""
    total = sum(len(k) + len(l) + 5 for k, l in hints) - 2
    x0 = cx - total // 2
    console.draw_rect(x0 - 1, y, total + 2, 1, ord(" "), bg=bg)
    hint_row(console, x0, y, hints, bg=bg)


def menu_row(console, x, y, w, label, *, selected=False, key=None,
             enabled=True, suffix="", suffix_fg=None):
    """One selectable row: highlighted bar when selected, dim when disabled."""
    bg = SEL_BG if selected else None
    if selected:
        console.draw_rect(x, y, w, 1, ord(" "), bg=SEL_BG)
    fg = (SEL_FG if selected else TEXT) if enabled else FAINT
    cx = x + 1
    console.print(x, y, "►" if selected else " ", fg=KEY, bg=bg)
    if key is not None:
        console.print(cx + 1, y, key, fg=KEY if enabled else FAINT, bg=bg)
        cx += len(key) + 3
    else:
        cx += 1
    console.print(cx, y, clip(label, w - (cx - x) - len(suffix) - 1), fg=fg, bg=bg)
    if suffix:
        console.print(x + w - len(suffix) - 1, y, suffix,
                      fg=suffix_fg or (DIM if enabled else FAINT), bg=bg)


def scrollbar(console, x, y, h, offset, visible, total, fg=BORDER, bg=None):
    """Thin vertical scrollbar; drawn only when content overflows."""
    if total <= visible or h <= 0:
        return
    for i in range(h):
        console.print(x, y + i, "│", fg=FAINT, bg=bg)
    thumb_h = max(1, h * visible // total)
    max_off = max(1, total - visible)
    thumb_y = y + (h - thumb_h) * offset // max_off
    for i in range(thumb_h):
        console.print(x, thumb_y + i, "█", fg=fg, bg=bg)


# ---------------------------------------------------------------------------
# Message colouring (log lines are plain strings)
# ---------------------------------------------------------------------------

_BAD_WORDS = ("warning", "missed", "not enough", "no fuel", "interest",
              "bounty", "collectors", "need ", "can't", "isn't", "don't",
              "repairs cost", "defeat", "no civilian")
_GOOD_WORDS = ("complete", "sold", "salvage", "paid off", "refueled",
               "received", "accepted", "escaped", "bought", "+")
_INFO_WORDS = ("jumped", "arrived", "docked", "deducted")


def message_color(msg):
    m = msg.lower()
    if any(w in m for w in _BAD_WORDS):
        return BAD
    if any(w in m for w in _GOOD_WORDS):
        return GOOD
    if any(w in m for w in _INFO_WORDS):
        return ACCENT
    return TEXT


# ---------------------------------------------------------------------------
# Charts (half-block resolution: each cell is two vertical steps)
# ---------------------------------------------------------------------------

def _resample(values, w):
    values = list(values)[-w:]
    return values


def chart(console, x, y, w, h, values, *, fg=None, bg=None, axis=True, min_span=0.0):
    """Column chart of the last w values in a w x h box.

    Colour is green if the series ends above where it started, red if below,
    unless fg is given. With axis=True the max/min are printed on the right
    (the chart is then 7 cells narrower).
    """
    values = [v for v in values if v is not None]
    if not values:
        return
    cw = w - 8 if axis else w
    vals = _resample(values, cw)
    lo, hi = min(vals), max(vals)
    # min_span: smallest range shown, as a fraction of the mean (stops tiny
    # wobbles from looking like crashes)
    span = abs(sum(vals) / len(vals)) * min_span
    if hi - lo < span:
        mid = (hi + lo) / 2
        lo, hi = mid - span / 2, mid + span / 2
    if hi - lo < 1e-9:
        hi, lo = hi + 1, lo - 1
    color = fg or (GOOD if vals[-1] >= vals[0] else BAD)
    levels = h * 2
    offset = cw - len(vals)
    for i, v in enumerate(vals):
        lvl = 1 + int(round((v - lo) / (hi - lo) * (levels - 1)))
        cx = x + offset + i
        for row in range(h):
            cy = y + h - 1 - row
            full, half = 2 * row + 2, 2 * row + 1
            ch = "█" if lvl >= full else ("▄" if lvl == half else None)
            if ch:
                shade = 0.55 + 0.45 * (i / max(1, len(vals) - 1))
                console.print(cx, cy, ch, fg=scale_color(color, shade), bg=bg)
    if axis:
        fmt = (lambda v: f"{v:,.0f}") if hi >= 100 else (lambda v: f"{v:.1f}")
        console.print(x + cw + 1, y, fmt(hi)[:7], fg=DIM, bg=bg)
        console.print(x + cw + 1, y + h - 1, fmt(lo)[:7], fg=DIM, bg=bg)
        for row in range(h):
            console.print(x + cw, y + row, "┤" if row in (0, h - 1) else "│", fg=FAINT, bg=bg)


def spark(console, x, y, w, values, *, fg=None, bg=None):
    """Two-row mini chart (4 levels)."""
    chart(console, x, y, w, 2, values, fg=fg, bg=bg, axis=False)


def pct(v):
    """+3.2% style string."""
    return f"{v * 100:+.1f}%"


def pct_color(v):
    return GOOD if v > 0.0005 else BAD if v < -0.0005 else DIM
