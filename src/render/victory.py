"""Render the VICTORY screen: the loan is paid off and the ship is yours."""

import math
import time

from core import state
from render import ui

SHIP = [
    r"     /\     ",
    r"    /  \    ",
    r"   | () |   ",
    r"  /|    |\  ",
    r" /_|_/\_|_\ ",
    r"   /_||_\   ",
]


def draw(console, width, height):
    bg = (10, 24, 18)
    console.draw_rect(0, 0, width, height, ord(" "), bg=(6, 14, 10))
    t = time.time()
    W, H = 64, 26
    x, y = (width - W) // 2, (height - H) // 2
    ui.frame(console, x, y, W, H, "Loan cleared", fg=(60, 160, 90), bg=bg,
             title_fg=ui.GOOD)

    pulse = 0.75 + 0.25 * math.sin(t * 2.5)
    for i, line in enumerate(SHIP):
        ui.center(console, x + W // 2, y + 2 + i, line,
                  fg=ui.scale_color((90, 220, 140), pulse), bg=bg)

    ui.center(console, x + W // 2, y + 9, "T H E   S H I P   I S   Y O U R S",
              fg=ui.GOOD, bg=bg)
    ui.paragraph(console, x + 6, y + 11, W - 12,
                 "The last credit is paid. The Rogue belongs to you now - "
                 "no debt, no deadlines, just the open dark.",
                 fg=ui.TEXT, max_lines=3, bg=bg)

    ix, iw = x + 10, W - 20
    ui.kv(console, ix, y + 15, iw, "Days taken", state.day, bg=bg)
    ui.kv(console, ix, y + 16, iw, "Credits", f"{ui.fmt_int(state.credits)} cr",
          value_fg=ui.KEY, bg=bg)
    ui.kv(console, ix, y + 17, iw, "Contracts completed",
          len(state.completed_mission_keys), bg=bg)
    ui.kv(console, ix, y + 18, iw, "Loan repaid", f"{ui.fmt_int(state.starting_debt)} cr",
          value_fg=ui.GOOD, bg=bg)

    ui.hint_row_centered(console, x + W // 2, y + H - 2,
                         [("C", "Keep flying"), ("Q", "Main menu")], bg=bg)
