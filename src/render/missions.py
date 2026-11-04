"""Render the MISSIONS board: contract list on the left, details on the right."""

from core import state
from core.entities import ITEMS
from render import ui

W, H = 76, 30
LIST_W = 32


def mission_tag(m):
    """Short status tag + colour for a contract."""
    here = state.current_location and m.destination == state.current_location.name
    if m.status == "available":
        return "NEW", ui.ACCENT
    if m.status == "active" and here:
        return "DELIVER", ui.GOOD
    if m.status == "active":
        return "ACTIVE", ui.KEY
    if m.status == "completed":
        return "DONE", ui.FAINT
    return m.status.upper(), ui.DIM


def difficulty(console, x, y, level):
    for i in range(3):
        console.print(x + i * 2, y, "■" if i < level else "·",
                      fg=(ui.GOOD, ui.WARN, ui.BAD)[level - 1] if i < level else ui.FAINT)


def draw(console, width, height=ui.MAP_H):
    loc = state.current_location
    x, y = ui.window(console, W, H, "Missions Board",
                     right_title=loc.name if loc else "")
    if loc is not None:
        from render.location import station_tabs
        station_tabs(console, x, y - 2, W)
    ix = x + 2

    # vertical divider
    dx = x + LIST_W + 2
    console.print(dx, y, "╦", fg=ui.BORDER_HI)
    for i in range(1, H - 3):
        console.print(dx, y + i, "║", fg=ui.BORDER_HI)
    ui.hline(console, x, y + H - 3, W, fg=ui.BORDER_HI)
    console.print(dx, y + H - 3, "╩", fg=ui.BORDER_HI)

    missions = state.visible_missions
    if not missions:
        ui.text(console, ix, y + 2, "No contracts posted.", fg=ui.DIM)
        ui.paragraph(console, dx + 2, y + 2, W - LIST_W - 6,
                     "The board is empty. Try another station, or come back "
                     "after a few days.", fg=ui.DIM)
        ui.hint_row_centered(console, x + W // 2, y + H - 2, [("ESC", "Back")])
        return

    # --- list ------------------------------------------------------------------
    ui.text(console, ix, y + 1, "CONTRACTS", fg=ui.DIM)
    for i, m in enumerate(missions):
        ry = y + 3 + i * 2
        if ry >= y + H - 4:
            break
        tag, tfg = mission_tag(m)
        sel = i == state.selected_mission_index
        ui.menu_row(console, ix - 1, ry, LIST_W + 1, m.title, selected=sel,
                    suffix=tag, suffix_fg=tfg, enabled=m.status != "completed")
        ui.text(console, ix + 2, ry + 1,
                ui.clip(f"{m.reward_credits} cr → {m.dest_system}", LIST_W - 3),
                fg=ui.DIM)

    # --- details ---------------------------------------------------------------
    m = missions[state.selected_mission_index]
    rx, rw = dx + 2, W - LIST_W - 6
    tag, tfg = mission_tag(m)
    ui.text(console, rx, y + 1, ui.clip(m.title.upper(), rw - len(tag) - 1), fg=ui.TITLE)
    ui.right(console, rx + rw - 1, y + 1, tag, fg=tfg)
    used = ui.paragraph(console, rx, y + 3, rw, m.description, fg=ui.TEXT, max_lines=5)

    ry = y + 4 + used
    ui.kv(console, rx, ry, rw, "Reward", f"{ui.fmt_int(m.reward_credits)} cr", value_fg=ui.KEY)
    ui.text(console, rx, ry + 1, "Difficulty", fg=ui.DIM)
    difficulty(console, rx + rw - 5, ry + 1, m.difficulty)
    ui.kv(console, rx, ry + 2, rw, "Destination", m.destination)
    if getattr(m, "dest_system", None):
        ui.kv(console, rx, ry + 3, rw, "System", m.dest_system, value_fg=ui.ACCENT)
    if m.mission_type == "cargo" and m.cargo:
        size = ITEMS[m.cargo].size * m.amount
        free = state.inventory.free_space()
        ui.kv(console, rx, ry + 5, rw, "Cargo", f"{m.amount}x {m.cargo}")
        ui.kv(console, rx, ry + 6, rw, "Hold space", f"{size} (free {free})",
              value_fg=ui.GOOD if free >= size or m.status != "available" else ui.BAD)

    # action line
    ay = y + H - 5
    if m.status == "available":
        ui.key_hint(console, rx, ay, "ENTER", "Accept contract")
    elif tag == "DELIVER":
        ui.key_hint(console, rx, ay, "ENTER", "Deliver cargo")
    elif m.status == "active":
        ui.text(console, rx, ay, ui.clip(f"Deliver at {m.destination}", rw), fg=ui.DIM)

    ui.hint_row_centered(console, x + W // 2, y + H - 2,
                         [("↑↓", "Select"), ("ENTER", "Accept/Deliver"),
                          ("V", "Map"), ("TAB", "Next"), ("ESC", "Station")])
