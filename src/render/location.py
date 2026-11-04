"""Render the LOCATION screen: the docked station / planet menu window."""

from core import state
from core.world import FUEL_PRICES
from render import ui

# key, label, action id  (the action ids are handled in core/events.py)
LOCATION_ITEMS = [
    ("1", "Trading Post", "market"),
    ("2", "Shipyard", "shipyard"),
    ("3", "Missions Board", "missions"),
    ("4", "Bar", "bar"),
    ("5", "Refuel", "refuel"),
    ("6", "Pay Debt", "debt"),
]

W, H = 54, 23


def item_status(action):
    """Return (enabled, suffix, suffix_fg) for a menu row."""
    loc = state.current_location
    if action == "market":
        if not loc.market:
            return False, "no market", ui.FAINT
        return True, f"{len(loc.market)} goods", ui.DIM
    if action == "missions":
        n = sum(1 for m in state.missions
                if m.status == "available" and m.source == loc.name)
        deliver = sum(1 for m in state.missions
                      if m.status == "active" and m.destination == loc.name)
        if deliver:
            return True, f"{deliver} to deliver!", ui.GOOD
        return True, f"{n} posted" if n else "browse", ui.DIM
    if action == "refuel":
        price = FUEL_PRICES.get(state.current_system.archetype)
        if price is None:
            return False, "unavailable", ui.FAINT
        need = state.max_fuel - state.fuel
        if need <= 0.01:
            return False, "tank full", ui.FAINT
        cost = need * price
        fg = ui.GOOD if state.credits >= cost else ui.BAD
        return True, f"{ui.fmt_int(cost)} cr ({price}/u)", fg
    if action == "shipyard":
        from core import shipyard
        n = shipyard.available_count()
        return True, f"{n} upgrade{'s' if n != 1 else ''}" if n else "fully fitted", ui.DIM
    if action == "debt":
        if state.debt <= 0:
            return False, "paid off", ui.FAINT
        return True, f"{ui.fmt_int(state.debt)} cr owed", ui.WARN
    return False, "closed", ui.FAINT


def _draw_debt(console, ix, iw, y):
    """The amount panel that replaces the menu while paying the loan."""
    ui.text(console, ix, y + 7, "PAY DOWN YOUR LOAN", fg=ui.KEY)
    ui.kv(console, ix, y + 9, iw, "Debt remaining", f"{ui.fmt_int(state.debt)} cr", value_fg=ui.TEXT)
    ui.kv(console, ix, y + 10, iw, "Your credits", ui.fmt_int(state.credits), value_fg=ui.KEY)
    ui.text(console, ix, y + 12, "Pay:", fg=ui.DIM)
    ui.text(console, ix + 6, y + 12, (state.debt_input or "") + "_", fg=ui.KEY)
    left = max(0, state.loan_deadline_day - state.day)
    ui.kv(console, ix, y + 14, iw, "Deadline",
          f"Day {state.loan_deadline_day} ({left} days left)",
          value_fg=ui.BAD if left <= 7 else (ui.WARN if left <= 30 else ui.TEXT))


def station_tabs(console, x, y, w):
    """Tabs shown above every docked screen, so they read as one place:
    TAB / Shift+TAB move between them, 1-5 jump straight to a facility."""
    loc = state.current_location
    tabs = [("", "Station", "LOCATION", "")]
    if loc is not None and loc.market:
        tabs.append(("1", "Trade", "MARKET", ""))
    tabs.append(("3", "Missions", "MISSIONS", ""))
    from core import travel
    price, cost = travel.refuel_cost()
    fuel_text = "n/a" if price is None else ("full" if state.fuel >= state.max_fuel - 0.01
                                             else f"{ui.fmt_int(cost)} cr")
    tabs.append(("5", "Refuel", None, fuel_text))
    ui.tab_strip(console, x, y, w, tabs, state.game_state)


def draw(console, width, height=ui.MAP_H):
    loc = state.current_location
    if loc is None:
        return
    kind = "Planet" if hasattr(loc, "govement") else "Station"
    owner = getattr(loc, "govement", None) or getattr(loc, "faction", "")

    x, y = ui.window(console, W, H, loc.name, right_title=kind)
    station_tabs(console, x, y - 2, W)
    ix, iw = x + 3, W - 6

    ui.text(console, ix, y + 2, f"{owner}", fg=ui.ACCENT)
    ui.right(console, x + W - 4, y + 2, f"{state.current_system.name} system", fg=ui.DIM)
    ui.text(console, ix, y + 3, "Docking clamps engaged. Welcome, pilot.", fg=ui.DIM)
    ui.hline(console, x, y + 5, W, fg=ui.BORDER_HI)

    if state.debt_input is not None:
        _draw_debt(console, ix, iw, y)
    else:
        for i, (key, label, action) in enumerate(LOCATION_ITEMS):
            enabled, suffix, sfg = item_status(action)
            ui.menu_row(console, ix - 1, y + 7 + i * 2, iw + 2, label,
                        selected=(i == state.location_index), key=key,
                        enabled=enabled, suffix=suffix, suffix_fg=sfg)

    ui.hline(console, x, y + H - 4, W, fg=ui.BORDER_HI)
    ui.kv(console, ix, y + H - 3, 20, "Credits", ui.fmt_int(state.credits), value_fg=ui.KEY)
    ui.kv(console, ix + iw - 18, y + H - 3, 18, "Fuel",
          f"{state.fuel:.0f}/{state.max_fuel:.0f}",
          value_fg=ui.ratio_color(state.fuel / state.max_fuel))
    if state.debt_input is not None:
        hints = [("0-9", "Amount"), ("M", "Max"), ("ENTER", "Pay"), ("ESC", "Cancel")]
    else:
        hints = [("↑↓", "Select"), ("ENTER", "Open"), ("TAB", "Next"), ("ESC", "Undock")]
    ui.hint_row_centered(console, x + W // 2, y + H - 1, hints)
