"""Render the INVENTORY overlay: cargo hold and ship systems."""

from collections import Counter

from core import state
from core.entities import ITEMS
from render import ui

W, H = 60, 34


def draw(console, width, height=ui.MAP_H):
    x, y = ui.window(console, W, H, "Cargo Hold",
                     right_title=f"{state.player_ship.name}")
    ix, iw = x + 3, W - 6
    inv = state.inventory
    used, cap = inv.used_space(), inv.space

    ui.kv(console, ix, y + 2, iw, "Capacity", f"{used}/{cap} units",
          value_fg=ui.ACCENT if used < cap else ui.WARN)
    ui.bar(console, ix, y + 3, iw, used, cap, ui.ACCENT if used < cap else ui.WARN)

    # header
    ui.text(console, ix, y + 5, "ITEM", fg=ui.DIM)
    ui.right(console, ix + 27, y + 5, "QTY", fg=ui.DIM)
    ui.right(console, ix + 35, y + 5, "SPACE", fg=ui.DIM)
    ui.text(console, ix + 38, y + 5, "SHARE", fg=ui.DIM)
    console.print(ix, y + 6, "─" * iw, fg=ui.BORDER)

    counts = Counter(item.name for item in inv.items)
    reserved = Counter()
    for m in state.missions:
        if m.status == "active" and m.mission_type == "cargo" and m.cargo:
            reserved[m.cargo] += m.amount

    if not counts:
        ui.text(console, ix, y + 7, "The hold is empty.", fg=ui.DIM)
    for i, (name, n) in enumerate(sorted(counts.items())):
        ry = y + 7 + i
        if ry >= y + 21:
            break
        space = ITEMS[name].size * n if name in ITEMS else n
        ui.text(console, ix, ry, name, fg=ui.TEXT)
        if reserved.get(name):
            ui.text(console, ix + len(name) + 1, ry, f"({min(n, reserved[name])} contract)",
                    fg=ui.KEY)
        ui.right(console, ix + 27, ry, str(n), fg=ui.TEXT)
        ui.right(console, ix + 35, ry, str(space), fg=ui.DIM)
        ui.bar(console, ix + 38, ry, iw - 38, space, cap, ui.ACCENT)

    # --- ship systems ------------------------------------------------------
    ship = state.player_ship
    sy = y + 22
    ui.hline(console, x, sy, W, fg=ui.BORDER_HI)
    ui.text(console, ix, sy + 1, "SHIP SYSTEMS", fg=ui.DIM)
    half = iw // 2 - 2
    ui.meter(console, ix, sy + 2, "Hull", ship.hull, ship.max_hull, half)
    ui.meter(console, ix + half + 4, sy + 2, "Fuel", state.fuel, state.max_fuel, half,
             fmt="{:.1f}/{:.0f}")
    ui.kv(console, ix, sy + 5, half, "Attack", ship.attack)
    ui.kv(console, ix, sy + 6, half, "Defense", ship.defense)
    ui.kv(console, ix + half + 4, sy + 5, half, "Engine", ship.engine)
    ui.kv(console, ix + half + 4, sy + 6, half, "Credits",
          ui.fmt_int(state.credits), value_fg=ui.KEY)

    ui.hint_row_centered(console, x + W // 2, y + H - 2, [("I", "Close"), ("ESC", "Close")])
