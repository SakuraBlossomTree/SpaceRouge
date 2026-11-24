"""Small moving details: rolling numbers, ship trail, ripples.

Like transitions.py these are time-based and keep only a tiny bit of state
between frames (what a number was a moment ago, where the ship has been), so
the renderers just ask "what should I draw right now?".
"""

import math
import time

from core import state

_EMPTY = (0, 32, ord("."), ord("·"), ord("'"))


def _lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _put(console, x, y, ch, fg, *, over=_EMPTY):
    """Print one glyph, but only on an empty-ish cell (never over text)."""
    if 0 <= x < console.width and 0 <= y < console.height:
        if int(console.rgb["ch"][y, x]) in over:
            console.print(x, y, ch, fg=fg)


# ---------------------------------------------------------------------------
# Rolling numbers: credits tick up / down, bars slide
# ---------------------------------------------------------------------------

_roll = {}      # key -> {"shown", "target", "last", "changed", "dir"}


def rolling(key, target, tau=0.25, snap=0.5):
    """A value that eases toward `target` instead of jumping to it."""
    now = time.time()
    r = _roll.get(key)
    if r is None or now - r["last"] > 1.5:     # first sight / screen was away
        _roll[key] = {"shown": target, "target": target, "last": now,
                      "changed": 0.0, "dir": 0}
        return target
    if r["target"] != target:
        r["dir"] = 1 if target > r["target"] else -1
        r["target"] = target
        r["changed"] = now
    dt = now - r["last"]
    r["last"] = now
    r["shown"] += (target - r["shown"]) * (1 - math.exp(-dt / tau))
    if abs(target - r["shown"]) < snap:
        r["shown"] = target
    return r["shown"]


def recent_change(key, window=0.9):
    """(+1 | -1 | 0, strength 1 -> 0) for a value that just changed."""
    r = _roll.get(key)
    if r is None or not r["dir"]:
        return 0, 0.0
    age = time.time() - r["changed"]
    if age > window:
        return 0, 0.0
    return r["dir"], 1.0 - age / window


# ---------------------------------------------------------------------------
# Ship trail
# ---------------------------------------------------------------------------

_trail = []     # (x, y, time)
_trail_system = None
TRAIL_LIFE = 1.1


def draw_trail(console, px, py, system_name):
    """Glowing wake behind the ship; fades over about a second."""
    global _trail_system
    now = time.time()
    if system_name != _trail_system:
        _trail.clear()
        _trail_system = system_name
    if not _trail or (_trail[-1][0], _trail[-1][1]) != (px, py):
        _trail.append((px, py, now))
    while _trail and now - _trail[0][2] > TRAIL_LIFE:
        _trail.pop(0)
    for x, y, t0 in _trail[:-1]:
        k = (now - t0) / TRAIL_LIFE
        glyph = "•" if k < 0.3 else ("∙" if k < 0.6 else "·")
        _put(console, x, y, glyph, _lerp((255, 220, 120), (40, 50, 80), k))


# ---------------------------------------------------------------------------
# Ripples and orbiting sparkles
# ---------------------------------------------------------------------------

def ripple(console, cx, cy, age, *, life=0.8, reach=9, color=(255, 235, 120)):
    """An expanding ring (arrival, selection)."""
    if age < 0 or age > life:
        return
    p = age / life
    r = 1 + p * reach
    fade = _lerp(color, (20, 24, 40), p)
    n = max(12, int(r * 7))
    for k in range(n):
        a = 2 * math.pi * k / n
        _put(console, int(round(cx + math.cos(a) * r)),
             int(round(cy + math.sin(a) * r)), "·", fade)


def pulse_ring(console, cx, cy, t, *, color=(255, 205, 90), reach=3, speed=1.6):
    """A repeating small ring: 'fly here' marker."""
    p = (t * speed) % 1.0
    ripple(console, cx, cy, p, life=1.0, reach=reach, color=color)


_ORBIT = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def orbit(console, cx, cy, t, *, color, speed=3.0, phase=0.0, count=2):
    """Dots circling a cell at distance one."""
    for k in range(count):
        dx, dy = _ORBIT[int(t * speed + phase + k * len(_ORBIT) / count) % 8]
        _put(console, cx + dx, cy + dy, "·", color)
