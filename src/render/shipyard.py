"""Render the SHIPYARD: buy simple ship upgrades."""

from core import state, shipyard
from render import ui

W, H = 62, 27


def draw(console, width, height=ui.MAP_H):
    loc = state.current_location
    if loc is None:
        return
    x, y = ui.window(console, W, H, f"{loc.name} · Shipyard",
                     right_title=state.current_system.archetype)
    from render.location import station_tabs
    station_tabs(console, x, y - 2, W)
    ix, iw = x + 3, W - 6

    ui.text(console, ix, y + 2, "Fit your ship. Upgrades are permanent.", fg=ui.DIM)
    ui.hline(console, x, y + 3, W, fg=ui.BORDER_HI)

    state.shipyard_index = max(0, min(state.shipyard_index, len(shipyard.UPGRADES) - 1))
    for i, (uid, name, offers) in enumerate(shipyard.UPGRADES):
        lv = shipyard.level(uid)
        pips = "■" * lv + "·" * (len(offers) - lv)
        offer = shipyard.next_offer(uid)
        if offer is None:
            suffix, sfg = "FITTED", ui.GOOD
        else:
            suffix = f"{ui.fmt_int(offer[0])} cr"
            sfg = ui.GOOD if state.credits >= offer[0] else ui.BAD
        ui.menu_row(console, ix - 1, y + 5 + i * 2, iw + 2, f"{name}  {pips}",
                    selected=(i == state.shipyard_index), enabled=offer is not None,
                    suffix=suffix, suffix_fg=sfg)

    uid, name, offers = shipyard.UPGRADES[state.shipyard_index]
    offer = shipyard.next_offer(uid)
    ui.hline(console, x, y + 15, W, fg=ui.BORDER_HI)
    ui.text(console, ix, y + 16, name.upper(), fg=ui.TITLE)
    ui.kv(console, ix, y + 17, iw, "Now", shipyard.current_text(uid))
    if offer is None:
        ui.kv(console, ix, y + 18, iw, "Next", "fully upgraded", value_fg=ui.GOOD)
    else:
        afford = state.credits >= offer[0]
        ui.kv(console, ix, y + 18, iw, "Next", offer[1])
        ui.kv(console, ix, y + 19, iw, "Price", f"{ui.fmt_int(offer[0])} cr",
              value_fg=ui.GOOD if afford else ui.BAD)

    ui.hline(console, x, y + 21, W, fg=ui.BORDER_HI)
    ui.kv(console, ix, y + 22, 24, "Credits", ui.fmt_int(state.credits), value_fg=ui.KEY)
    ui.kv(console, ix + iw - 22, y + 22, 22, "Upgrades left", shipyard.available_count())

    ui.hint_row_centered(console, x + W // 2, y + H - 1,
                         [("↑↓", "Select"), ("ENTER", "Buy"), ("TAB", "Next screen"),
                          ("ESC", "Station")])
