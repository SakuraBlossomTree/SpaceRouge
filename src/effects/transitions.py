"""Screen and menu transitions.

Everything here is time-based and stateless between frames except for one
tiny table: when a watched value (the game state, "is the quick menu open")
changes, the time of the change is remembered, so any renderer can ask "how
long ago did this open?" and animate accordingly.

    touch("screen", state.game_state)      # call once per frame
    p = progress("screen", 0.25)           # 0 -> 1 over a quarter second

Effects work on a finished console, so no screen needs to know about them:

    unfold(console, under, p)   a menu opens outward from its centre line
    fade_in(console, p)         a screen fades up from black
    flash_in(console, p)        a screen fades up from white
"""

import time

import numpy as np

_seen = {}   # channel -> (value, time of change, previous value)


def touch(channel, value):
    """Record the current value of a channel; remembers when it last changed."""
    rec = _seen.get(channel)
    if rec is None:
        _seen[channel] = (value, time.time(), None)
    elif rec[0] != value:
        _seen[channel] = (value, time.time(), rec[0])


def age(channel):
    rec = _seen.get(channel)
    return 999.0 if rec is None else time.time() - rec[1]


def previous(channel):
    rec = _seen.get(channel)
    return None if rec is None else rec[2]


def progress(channel, duration):
    """0.0 just after the channel changed, 1.0 once `duration` has passed."""
    return max(0.0, min(1.0, age(channel) / duration))


def ease_out(p):
    return 1.0 - (1.0 - p) ** 3


def _rows_axis(console):
    """console.rgb is [y, x] normally; be safe if a tcod build uses [x, y]."""
    return 0 if console.rgb.shape[0] == console.height else 1


def unfold(console, under, p, edge=(120, 215, 255)):
    """Reveal what is on the console from its centre line outward.

    `under` is a copy of console.rgb taken before the menu was drawn. Rows the
    animation hasn't reached yet get their old contents back, and a thin glowing
    scan line marks the moving edge.
    """
    if p >= 1.0:
        return
    arr = console.rgb
    h = console.height
    rows = np.abs(np.arange(h) - (h - 1) / 2.0)
    half = ease_out(p) * (h / 2.0)
    hidden = rows > half
    near_edge = (~hidden) & (rows > half - 1.0)

    def mask(row_flags):
        if _rows_axis(console) == 0:
            return np.broadcast_to(row_flags[:, None], arr.shape)
        return np.broadcast_to(row_flags[None, :], arr.shape)

    hm = mask(hidden)
    arr[hm] = under[hm]
    em = mask(near_edge)
    if em.any():
        glow = tuple(int(c * (1.0 - p)) for c in edge)
        arr["ch"][em] = ord("═")
        arr["fg"][em] = glow
        arr["bg"][em] = tuple(int(c * 0.12) for c in glow)


def fade_in(console, p):
    """Fade the console up from black (p=0 black, p=1 untouched)."""
    if p >= 1.0:
        return
    arr = console.rgb
    arr["fg"] = (arr["fg"] * p).astype("u1")
    arr["bg"] = (arr["bg"] * p).astype("u1")


def whiten(console, amount):
    """Blend the console toward white (amount 0 = untouched, 1 = all white)."""
    if amount <= 0.0:
        return
    amount = min(1.0, amount)
    arr = console.rgb
    for key in ("fg", "bg"):
        c = arr[key].astype("f4")
        arr[key] = (c + (255.0 - c) * amount).astype("u1")


def flash_in(console, p):
    """Fade the console down from white (p=0 white, p=1 untouched)."""
    whiten(console, 1.0 - p)
