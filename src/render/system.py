"""Render the SYSTEM screen: planets, spinning stations, jump gates, player.

Draws into the 80x60 map viewport console using world coordinates.
"""

import random
import time
import zlib

import numpy as np

from core import state, look
from effects.effects import get_spin_frame, twinkle_color
from render import ui

LABEL_FG = (95, 105, 135)
GATE_FG = (90, 210, 220)

_bg_cache = {}


def _background(name, width, height):
    """Deterministic faint starfield per system (cached)."""
    key = (name, width, height)
    if key not in _bg_cache:
        rng = random.Random(zlib.crc32(name.encode()))
        dots = []
        for _ in range(width * height // 28):
            x, y = rng.randrange(width), rng.randrange(height)
            ch = rng.choice("..·.·'")
            b = rng.randint(28, 70)
            tint = rng.choice([(1, 1, 1.3), (1.2, 1, 1), (1, 1, 1)])
            color = tuple(min(255, int(b * t)) for t in tint)
            dots.append((x, y, ch, color, rng.uniform(0, 6.28)))
        _bg_cache[key] = dots
    return _bg_cache[key]


_bg_arrays = {}


def draw_background(console, name, width, height, t=None, speed=0.7):
    """Draw a system's faint starfield in one go (numpy instead of a print per
    dot - much faster, which matters on phones). t=None: no twinkle."""
    key = (name, width, height)
    if key not in _bg_arrays:
        dots = _background(name, width, height)
        _bg_arrays[key] = (
            np.array([d[0] for d in dots], dtype=np.intp),
            np.array([d[1] for d in dots], dtype=np.intp),
            np.array([ord(d[2]) for d in dots], dtype=np.int32),
            np.array([d[3] for d in dots], dtype=np.float32).reshape(-1, 3),
            np.array([d[4] for d in dots], dtype=np.float32),
        )
    xs, ys, codes, cols, phase = _bg_arrays[key]
    m = (xs < console.width) & (ys < console.height)
    if t is None:
        fg = cols
    else:   # same curve as effects.twinkle_color
        k = 0.5 + 0.5 * (np.sin(t * speed + phase) + 1) / 2
        fg = cols * k[:, None]
    rgb = console.rgb
    rgb["ch"][ys[m], xs[m]] = codes[m]
    rgb["fg"][ys[m], xs[m]] = fg[m].astype(np.uint8)


def _label(console, x, y, text, fg, width):
    """Name tag to the right of an object (or left if it would overflow)."""
    lx = x + 2
    if lx + len(text) >= width:
        lx = x - 1 - len(text)
    console.print(max(0, lx), y, text, fg=fg)


def draw_cursor(console, x, y):
    """Highlight one cell as the look/scan cursor."""
    if 0 <= x < console.width and 0 <= y < console.height:
        blink = int(time.time() * 3) % 2 == 0
        ch = int(console.rgb["ch"][y, x])
        glyph = "+" if ch in (0, 32) else chr(ch)
        console.print(x, y, glyph, fg=(0, 0, 0),
                      bg=ui.KEY if blink else (150, 110, 30))


def draw(console, width, height, system):
    state.current_object = None
    look_object = None
    t = time.time()

    # --- background --------------------------------------------------------
    draw_background(console, system.name, width, height, t)

    objects = [*system.planets, *system.stations, *system.jump_points]

    # --- labels first so glyphs always sit on top ---------------------------
    for planet in system.planets:
        _label(console, planet.x, planet.y, planet.name, LABEL_FG, width)
    for station in system.stations:
        _label(console, station.x, station.y, station.name, LABEL_FG, width)
    for jp in system.jump_points:
        _label(console, jp.x, jp.y, f"→ {jp.destination}", (70, 130, 140), width)

    # --- objects -------------------------------------------------------------
    for planet in system.planets:
        console.print(planet.x, planet.y, "○", fg=ui.vivid(planet.color))

    for i, station in enumerate(system.stations):
        frame = get_spin_frame(t, speed=8.0, phase=3 + i)
        console.print(station.x, station.y, frame, fg=(235, 235, 245))

    for i, jp in enumerate(system.jump_points):
        color = twinkle_color(GATE_FG, t, speed=3.0, phase=i)
        console.print(jp.x, jp.y, "Θ", fg=color)

    for obj in objects:
        if state.system_player_x == obj.x and state.system_player_y == obj.y:
            state.current_object = obj
        look_object = look.check(obj, look_object)

    # --- player --------------------------------------------------------------
    px, py = state.system_player_x, state.system_player_y
    if state.current_object is not None:
        # docked-in-range: show the ship over a highlighted cell
        console.print(px, py, "@", fg=(0, 0, 0), bg=ui.PLAYER)
    else:
        console.print(px, py, "@", fg=ui.PLAYER)

    # --- autopilot target -----------------------------------------------------
    if state.autopilot is not None:
        tx, ty, _ = state.autopilot
        if 0 <= tx < width and 0 <= ty < height and (tx, ty) != (px, py):
            ch = int(console.rgb["ch"][ty, tx])
            blink = int(t * 4) % 2 == 0
            console.print(tx, ty, chr(ch) if ch not in (0, 32) else "◦",
                          fg=(0, 0, 0) if blink else ui.KEY, bg=ui.KEY if blink else None)

    # --- look cursor ---------------------------------------------------------
    state.look_object = look_object
    if state.look_mode:
        draw_cursor(console, state.look_x, state.look_y)

    # On-map prompt when something is in range (sidebar has the details)
    if state.current_object is not None and not state.look_mode:
        verb = "Jump menu" if hasattr(state.current_object, "destination") else "Dock"
        tag = f" ENTER: {verb} · {state.current_object.name} "
        tx = max(0, min(width - len(tag), px - len(tag) // 2))
        ty = py - 2 if py >= 3 else py + 2
        console.print(tx, ty, tag, fg=(0, 0, 0), bg=ui.GOOD)
