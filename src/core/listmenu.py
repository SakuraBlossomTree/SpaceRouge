"""Ship menu (S): a readable list window of the ship's everyday options.

    UP/DOWN/TAB  move   1-9 pick   ENTER choose   ESC or S again closes

SPACE (the quick menu) still lists everything; the ship menu links to it.
The menu is (title, subtitle, info rows, items). An item is a dict:
label, key, note, detail, enabled, action.
"""

import tcod

from core import state

K = tcod.event.KeySym


def _keys(*names):
    return [getattr(K, n) for n in names if hasattr(K, n)]


NUMBER_KEYS = {}
for _i in range(9):
    for _k in _keys(f"N{_i + 1}", f"KP_{_i + 1}"):
        NUMBER_KEYS[_k] = _i

DOCKED = ("LOCATION", "MARKET", "MISSIONS", "SHIPYARD")


def _item(label, key, action, *, note="", detail="", enabled=True):
    return {"label": label, "key": key, "note": note, "detail": detail,
            "enabled": enabled, "action": action}


# ---------------------------------------------------------------------------
# Ship menu
# ---------------------------------------------------------------------------

def ship_menu():
    from core import events, quickmenu, repair, travel
    docked = state.game_state in DOCKED and state.current_location is not None
    ship = state.player_ship
    price, cost = travel.refuel_cost() if docked else (None, 0)
    full = state.fuel >= state.max_fuel - 0.01
    if not docked:
        fuel_note = repair_note = "dock first"
    else:
        fuel_note = "not sold here" if price is None else ("tank full" if full else f"{cost:,} cr")
        repair_note = "hull intact" if repair.damage() <= 0 else f"{repair.cost():,} cr"
    active = sum(1 for m in state.missions if m.status == "active")
    where = state.current_location.name if docked else (
        state.current_system.name if state.current_system else "")
    info = [("Credits", f"{state.credits:,}"),
            ("Fuel", f"{state.fuel:.0f}/{state.max_fuel:.0f}"),
            ("Hull", f"{ship.hull}/{ship.max_hull}"), ("Contracts", f"{active} active")]
    go = events.goto_screen
    items = [
        _item("Cargo hold", "I", lambda: go("INVENTORY"), detail="What you carry."),
        _item("Contracts", "P", lambda: go("MISSION_LOG"), note=f"{active} active",
              detail="Your accepted contracts and where to go."),
        _item("Galaxy chart", "M", lambda: go("GALAXY"), detail="Map, scanner and routes."),
        _item("Exchange", "E", lambda: go("EXCHANGE"), detail="Galactic Exchange prices."),
        _item("Refuel", "5", events.quick_refuel, note=fuel_note,
              enabled=docked and price is not None and not full,
              detail="Fill the tank at this station."),
        _item("Repair hull", "8", events._repair, note=repair_note,
              enabled=docked and repair.damage() > 0,
              detail="Pay credits to restore hull points."),
        _item("Comms log", "L", lambda: go("MESSAGES"), detail="Recent messages."),
        _item("Everything...", "SPACE", quickmenu.open_menu,
              detail="The full quick menu: every screen and place."),
    ]
    return "Ship", where, info, items


# ---------------------------------------------------------------------------
# Open / close / keys
# ---------------------------------------------------------------------------

def current():
    return ship_menu()


def _first_enabled(items):
    return next((i for i, it in enumerate(items) if it["enabled"]), 0)


def open_ship_menu():
    state.list_menu = "ship"
    state.list_menu_index = _first_enabled(current()[3])


def close():
    state.list_menu = None


def _step(items, step):
    for _ in range(len(items)):
        state.list_menu_index = (state.list_menu_index + step) % len(items)
        if items[state.list_menu_index]["enabled"]:
            break


def _choose(item):
    if not item["enabled"]:
        return
    close()
    item["action"]()


def handle(event):
    """Keys while a list menu is open. Always consumes the key."""
    sym = event.sym
    if sym in (K.ESCAPE, K.BACKSPACE, K.S):
        close()
        return
    items = current()[3]
    if not items:
        return
    state.list_menu_index %= len(items)
    if sym in (K.UP, K.W):
        _step(items, -1)
    elif sym == K.DOWN:
        _step(items, 1)
    elif sym == K.TAB:
        shift = bool(int(getattr(event, "mod", 0) or 0) & 0x0003)
        _step(items, -1 if shift else 1)
    elif sym in (K.RETURN, K.KP_ENTER):
        _choose(items[state.list_menu_index])
    elif sym in NUMBER_KEYS and NUMBER_KEYS[sym] < len(items):
        _choose(items[NUMBER_KEYS[sym]])
