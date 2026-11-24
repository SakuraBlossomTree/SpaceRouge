"""Render the autopilot wheel (TAB): places around a ring, the chosen one
joined to the hub by a spoke, with its details in the middle."""

import math
import time

from core import state, navwheel, travel
from effects import motion
from effects.effects import get_spin_frame
from effects import transitions as anim
from render import ui

OPEN_TIME = 0.28
KIND_GLYPH = {"planet": "○", "station": "-", "gate": "Θ"}   # stations spin, see _glyph
KIND_NAME = {"planet": "Planet", "station": "Station", "gate": "Jump gate"}
GATE_FG = (90, 210, 220)
STATION_FG = (235, 235, 245)


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _glyph(kind, obj, t):
    """Same symbols as the system map: stations spin like they do there."""
    if kind == "station":
        stations = state.current_system.stations
        i = stations.index(obj) if obj in stations else 0
        return get_spin_frame(t, speed=8.0, phase=3 + i)
    return KIND_GLYPH[kind]


def _kind_color(kind, obj):
    if kind == "planet":
        return ui.vivid(obj.color)
    return GATE_FG if kind == "gate" else STATION_FG


def draw(console):
    items = navwheel.places()
    if not items:
        return
    n = len(items)
    sel = state.nav_wheel_index % n
    t = time.time()
    grow = _ease((t - state.nav_wheel_opened) / OPEN_TIME)

    ui.dim_console(console, 0.3)
    cx, cy = console.width // 2, console.height // 2
    ry, rx = 17 * grow, 21 * grow          # a slightly wide ring

    # ring
    steps = 120
    for k in range(steps):
        a = 2 * math.pi * k / steps
        x = int(round(cx + math.cos(a) * rx))
        y = int(round(cy + math.sin(a) * ry))
        if 0 <= x < console.width and 0 <= y < console.height:
            console.print(x, y, "·", fg=ui.BORDER)

    # a bright dot sweeps round the ring, lighting the dots it passes
    sweep = (t * 0.6) % 1.0
    for k in range(steps):
        d = (k / steps - sweep) % 1.0
        if d < 0.12 and grow > 0.9:
            a = 2 * math.pi * k / steps
            x = int(round(cx + math.cos(a) * rx))
            y = int(round(cy + math.sin(a) * ry))
            if 0 <= x < console.width and 0 <= y < console.height:
                console.print(x, y, "•" if d < 0.02 else "·",
                              fg=ui.lerp_color(ui.ACCENT, ui.BORDER, d / 0.12))

    # spoke from the hub to the chosen place
    a_sel = navwheel.angle(sel, n)
    for k in range(1, 20):
        f = k / 20
        x = int(round(cx + math.cos(a_sel) * rx * f * 0.8))
        y = int(round(cy + math.sin(a_sel) * ry * f * 0.8))
        pulse = 0.5 + 0.5 * math.sin(t * 6 - k * 0.5)
        console.print(x, y, "·", fg=ui.lerp_color(ui.BORDER, ui.KEY, pulse))

    # places
    for i, (kind, obj, label, dist) in enumerate(items):
        a = navwheel.angle(i, n)
        x = int(round(cx + math.cos(a) * rx))
        y = int(round(cy + math.sin(a) * ry))
        selected = i == sel
        color = _kind_color(kind, obj)
        # places pop in one after another around the ring
        if (t - state.nav_wheel_opened) < 0.1 + 0.25 * i / n:
            continue
        if grow < 0.6:
            console.print(x, y, _glyph(kind, obj, t), fg=color)
            continue
        if selected:
            pulse = 0.5 + 0.5 * math.sin(t * 5)
            console.print(x - 1, y, "[", fg=ui.KEY)
            console.print(x + 1, y, "]", fg=ui.KEY)
            console.print(x, y, _glyph(kind, obj, t),
                          fg=ui.lerp_color(color, (255, 255, 255), pulse))
        else:
            console.print(x, y, _glyph(kind, obj, t), fg=color)
        tag = f"{i + 1}" if i < 9 else "-"
        text = ui.clip(f"{tag} {label}", 19)
        fg = ui.SEL_FG if selected else ui.DIM
        bg = ui.SEL_BG if selected else None
        if math.cos(a) >= -0.2:
            lx = x + 3
        else:
            lx = x - 3 - len(text) + 1
        lx = max(0, min(console.width - len(text), lx))
        console.print(lx, y, text, fg=fg, bg=bg)

    # a ring pops out of the place you just moved to
    anim.touch("wheelsel", sel)
    sx = int(round(cx + math.cos(a_sel) * rx))
    sy = int(round(cy + math.sin(a_sel) * ry))
    motion.ripple(console, sx, sy, anim.age("wheelsel"), life=0.35, reach=4,
                  color=ui.KEY)

    # hub
    kind, obj, label, dist = items[sel]
    ui.center(console, cx, cy - 2, "AUTOPILOT", fg=ui.TITLE)
    ui.center(console, cx, cy - 1, ui.clip(label, 24), fg=_kind_color(kind, obj))
    ui.center(console, cx, cy, KIND_NAME[kind], fg=ui.DIM)
    if dist == 0:
        info = "you are here"
    else:
        info = f"{dist} moves, no fuel"
        days = (state.move_counter + dist) // travel.MOVES_PER_DAY
        if days:
            info += f", {days} day{'s' if days != 1 else ''}"
    ui.center(console, cx, cy + 1, info, fg=ui.ACCENT)

    ui.hint_row_centered(console, cx, console.height - 2,
                         [("←→/TAB", "Choose"), ("1-9", "Pick"), ("ENTER", "Fly & dock"),
                          ("F", "Fly only"), ("ESC", "Close")], bg=None)
