"""Render the GAME OVER screen."""

import math
import time

from core import state
from render import ui

SKULL = [
    "   ______   ",
    "  /      \\  ",
    " |  X  X  | ",
    " |   /\\   | ",
    "  \\ ____ /  ",
    "   |||||    ",
]


def draw(console, width, height):
    console.draw_rect(0, 0, width, height, ord(" "), bg=(12, 2, 4))
    t = time.time()
    W, H = 64, 28
    x, y = (width - W) // 2, (height - H) // 2
    ui.frame(console, x, y, W, H, "Signal lost", fg=(140, 40, 40),
             bg=(20, 6, 8), title_fg=ui.BAD)
    bg = (20, 6, 8)

    pulse = 0.7 + 0.3 * math.sin(t * 3)
    for i, line in enumerate(SKULL):
        ui.center(console, x + W // 2, y + 2 + i, line,
                  fg=ui.scale_color((220, 70, 70), pulse), bg=bg)

    ui.center(console, x + W // 2, y + 9, "G A M E   O V E R", fg=ui.BAD, bg=bg)
    ui.paragraph(console, x + 6, y + 11, W - 12, state.game_over_reason or "",
                 fg=ui.TEXT, max_lines=3, bg=bg)

    ix, iw = x + 10, W - 20
    ui.kv(console, ix, y + 15, iw, "Days survived", state.day, bg=bg)
    ui.kv(console, ix, y + 16, iw, "Credits", f"{ui.fmt_int(state.credits)} cr",
          value_fg=ui.KEY, bg=bg)
    ui.kv(console, ix, y + 17, iw, "Debt remaining", f"{ui.fmt_int(state.debt)} cr",
          value_fg=ui.BAD, bg=bg)
    done = len(state.completed_mission_keys)
    ui.kv(console, ix, y + 18, iw, "Contracts completed", done, bg=bg)
    paid = max(0, state.starting_debt - state.debt)
    ui.bar(console, ix, y + 20, iw, paid, state.starting_debt, ui.GOOD, bg=bg)
    ui.center(console, x + W // 2, y + 21,
              f"{100 * paid / state.starting_debt:.1f}% of the loan repaid",
              fg=ui.DIM, bg=bg)

    ui.hint_row_centered(console, x + W // 2, y + H - 2, [("Q", "Main menu")], bg=bg)
