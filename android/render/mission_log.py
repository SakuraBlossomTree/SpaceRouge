"""Render the MISSION_LOG overlay: every active contract in detail."""

from core import state
from render import ui
from render.missions import difficulty

W, H = 64, 40


def draw(console, width, height=ui.MAP_H):
    H = min(40, ui.MAP_H - 2)        # fits shorter (mobile) screens
    active = [m for m in state.missions if m.status == "active"]
    done = sum(1 for m in state.missions if m.status == "completed")
    x, y = ui.window(console, W, H, "Contract Log",
                     right_title=f"{len(active)} active")
    ix, iw = x + 3, W - 6

    if not active:
        ui.center(console, x + W // 2, y + H // 2 - 1, "No active contracts.", fg=ui.DIM)
        ui.center(console, x + W // 2, y + H // 2 + 1,
                  "Dock at a station and open the Missions Board.", fg=ui.FAINT)
    cy = y + 2
    for m in active:
        if cy + 6 > y + H - 3:
            ui.text(console, ix, cy, f"+ {len(active)} more...", fg=ui.DIM)
            break
        here = state.current_system and m.dest_system == state.current_system.name
        ui.text(console, ix, cy, "■", fg=ui.GOOD if here else ui.KEY)
        ui.text(console, ix + 2, cy, m.title.upper(), fg=ui.TITLE)
        ui.right(console, ix + iw - 1, cy, f"{ui.fmt_int(m.reward_credits)} cr", fg=ui.KEY)
        used = ui.paragraph(console, ix + 2, cy + 1, iw - 2, m.description,
                            fg=ui.TEXT, max_lines=2)
        ui.text(console, ix + 2, cy + 1 + used,
                ui.clip(f"→ {m.destination}, {m.dest_system} system", iw - 10),
                fg=ui.GOOD if here else ui.DIM)
        difficulty(console, ix + iw - 5, cy + 1 + used, m.difficulty)
        if here:
            ui.text(console, ix + 2, cy + 2 + used, "Destination is in this system!",
                    fg=ui.GOOD)
            used += 1
        cy += used + 3

    ui.hline(console, x, y + H - 3, W, fg=ui.BORDER_HI)
    ui.text(console, ix, y + H - 2, f"Completed: {done}", fg=ui.DIM)
    ui.hint_row(console, x + W - 26, y + H - 2, [("P", "Close"), ("ESC", "Close")])
