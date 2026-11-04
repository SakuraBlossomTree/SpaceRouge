"""Render the JUMPPOINT screen: confirm a hyperspace jump."""

from core import state
from core.world import STAR_TYPES
from render import ui

W, H = 52, 19


def draw(console, width, height):
    jp = state.current_object
    if jp is None:
        return
    dest = next((s for s in state.stars if s.name == jp.destination), None)
    dest_color = STAR_TYPES[dest.type]["color"] if dest else ui.TEXT

    x, y = ui.window(console, W, H, jp.name, right_title="Jump gate")
    ix, iw = x + 3, W - 6

    # route
    origin = state.current_system.name
    ui.center(console, x + W // 2, y + 2, "HYPERSPACE ROUTE", fg=ui.DIM)
    route_y = y + 4
    left = f"☼ {origin}"
    rightt = f"{jp.destination} ☼"
    console.print(ix, route_y, left, fg=ui.PLAYER)
    console.print(x + W - 3 - len(rightt), route_y, rightt, fg=dest_color)
    gap_x0 = ix + len(left) + 1
    gap_x1 = x + W - 4 - len(rightt)
    if gap_x1 > gap_x0:
        console.print(gap_x0, route_y, "·" * (gap_x1 - gap_x0) + "►", fg=ui.ACCENT)

    ui.hline(console, x, y + 6, W, fg=ui.BORDER_HI)
    if dest:
        ui.kv(console, ix, y + 8, iw, "Destination", dest.name, value_fg=dest_color)
        ui.kv(console, ix, y + 9, iw, "Star class", dest.type)
        ui.kv(console, ix, y + 10, iw, "Economy", dest.system.archetype)

    from core import travel
    need = travel.jump_fuel(jp)
    fuel_ok = state.fuel >= need
    afford = state.credits >= jp.cost
    ui.kv(console, ix, y + 12, iw, "Gate toll", f"{jp.cost} cr",
          value_fg=ui.GOOD if afford else ui.BAD)
    ui.kv(console, ix, y + 13, iw, "Balance after",
          f"{ui.fmt_int(state.credits - jp.cost)} cr",
          value_fg=ui.TEXT if afford else ui.BAD)
    if travel.hard():
        ui.kv(console, ix, y + 14, iw, "Jump fuel", "none (Hard: flying burns fuel)",
              value_fg=ui.DIM)
    else:
        ui.kv(console, ix, y + 14, iw, "Jump fuel",
              f"{need}  (tank {state.fuel:.0f} → {max(0, state.fuel - need):.0f})",
              value_fg=ui.GOOD if fuel_ok else ui.BAD)
    ui.kv(console, ix, y + 15, iw, "Travel time", "1 day", value_fg=ui.DIM)

    if afford and fuel_ok:
        ui.hint_row_centered(console, x + W // 2, y + H - 2,
                             [("ENTER", "Engage jump"), ("ESC", "Cancel")])
    elif not fuel_ok:
        ui.center(console, x + W // 2, y + H - 2, "Not enough fuel - refuel at a station",
                  fg=ui.BAD)
    else:
        ui.center(console, x + W // 2, y + H - 2, "Not enough credits for the toll",
                  fg=ui.BAD)
