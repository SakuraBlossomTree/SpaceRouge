"""Render the TITLE screen: drifting starfield, gradient logo, menu."""

import math
import random
import time

from core import fonts, state, tutorial
from effects.effects import twinkle_color
from render import ui

_stars = None

LOGO_TOP = (90, 220, 255)
LOGO_BOTTOM = (200, 90, 255)


def _init_stars(width, height, count=220):
    rng = random.Random()
    stars = []
    for _ in range(count):
        depth = rng.choice((1, 1, 1, 2, 2, 3))
        stars.append({
            "x": rng.uniform(0, width),
            "y": rng.randrange(height),
            "depth": depth,
            "phase": rng.uniform(0, 6.28),
            "color": rng.choice([(255, 255, 255), (170, 200, 255),
                                 (255, 230, 180), (255, 180, 180)]),
        })
    return stars


def draw(console, width, height, title_text):
    global _stars
    t = time.time()
    if _stars is None:
        _stars = _init_stars(width, height)

    console.draw_rect(0, 0, width, height, ord(" "), bg=ui.BG)

    # parallax starfield drifting left
    for s in _stars:
        speed = (0.6, 1.6, 4.0)[s["depth"] - 1]
        x = int((s["x"] - t * speed) % width)
        ch = (".", "·", "*")[s["depth"] - 1]
        base = ui.scale_color(s["color"], (0.35, 0.6, 1.0)[s["depth"] - 1])
        console.print(x, s["y"], ch, fg=twinkle_color(base, t, 2.0, s["phase"]), bg=ui.BG)

    # logo with vertical gradient and a slow shimmer
    lines = title_text.rstrip("\n").split("\n")
    lw = max(len(l) for l in lines)
    lx = (width - lw) // 2
    ly = height // 2 - len(lines) - 6
    console.draw_rect(lx - 3, ly - 2, lw + 6, len(lines) + 4, ord(" "), bg=ui.BG)
    for i, line in enumerate(lines):
        for j, ch in enumerate(line):
            if ch == " ":
                continue
            k = i / max(1, len(lines) - 1)
            shimmer = 0.85 + 0.15 * math.sin(t * 2.0 - j * 0.15)
            fg = ui.scale_color(ui.lerp_color(LOGO_TOP, LOGO_BOTTOM, k), shimmer)
            console.print(lx + j, ly + i, ch, fg=fg, bg=ui.BG)

    tag = f"A TRADER'S ROGUELIKE  ·  {state.starting_debt:,} CREDITS IN DEBT  ·  ONE SHIP"
    ui.center(console, width // 2, ly + len(lines) + 1, tag, fg=ui.DIM, bg=ui.BG)

    # menu box
    bw, bh = 54, 13
    bx, by = (width - bw) // 2, ly + len(lines) + 5
    panel = (10, 14, 28)
    ui.frame(console, bx, by, bw, bh, fg=ui.BORDER, bg=panel)
    pulse = 0.6 + 0.4 * (math.sin(t * 4) + 1) / 2
    ui.center(console, width // 2, by + 2, "►  NEW GAME  ◄",
              fg=ui.scale_color(ui.KEY, pulse), bg=panel)

    ui.hint_row_centered(console, width // 2, by + 4,
                         [("ENTER", "Start"), ("F11", "Fullscreen"), ("Q", "Quit")],
                         bg=panel)
    on = tutorial.enabled()
    ui.hint_row_centered(console, width // 2, by + 6,
                         [("T", f"Tutorial: {'ON ' if on else 'OFF'}"),
                          ("F10", f"Font: {fonts.current_name()}")],
                         bg=panel)

    # galaxy seed: S to type one, L to replay last run's galaxy
    ui.hline(console, bx, by + 8, bw, fg=ui.BORDER, bg=panel)
    if state.seed_input is not None:
        cursor = "█" if int(t * 2) % 2 == 0 else " "
        ui.center(console, width // 2, by + 9, f"Seed: {state.seed_input}{cursor}",
                  fg=ui.KEY, bg=panel)
        ui.hint_row_centered(console, width // 2, by + 11,
                             [("0-9", "Type"), ("ENTER", "Load"), ("ESC", "Cancel")], bg=panel)
    elif on:
        ui.center(console, width // 2, by + 9, "Tutorial: practice galaxy first",
                  fg=ui.ACCENT, bg=panel)
        ui.center(console, width // 2, by + 11,
                  f"Then your real game, galaxy seed {state.galaxy_seed}",
                  fg=ui.DIM, bg=panel)
    else:
        ui.center(console, width // 2, by + 9, f"Galaxy seed {state.galaxy_seed}",
                  fg=ui.DIM, bg=panel)
        hints = [("S", "Enter seed")]
        if state.last_seed is not None and state.last_seed != state.galaxy_seed:
            hints.append(("L", f"Last galaxy ({state.last_seed})"))
        ui.hint_row_centered(console, width // 2, by + 11, hints, bg=panel)

    from core import audio
    muted = audio.music_muted()
    x = ui.key_hint(console, 2, height - 2, "F4", "Music: OFF" if muted else "Music: ON",
                    bg=ui.BG, label_fg=ui.BAD if muted else ui.DIM)
    ui.right(console, width - 2, height - 2, "v0.1 · made with python-tcod",
             fg=ui.FAINT, bg=ui.BG)
