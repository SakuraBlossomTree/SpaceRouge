"""Quick menu (SPACE): every screen, and every place in the system, one
press away.

    ↑↓ + ENTER   go there
    SPACE / ESC  close
    letter keys  the screen's usual shortcut works here too (M, I, P, ...)

The menu changes with where you are: docked, it lists the station's
facilities; in space, it lists the planets, stations and gates of the system
so the autopilot can fly you there (and dock / open the jump menu on arrival).
"""

import tcod

from core import state

K = tcod.event.KeySym

NOT_HERE = ("TITLE", "STORY", "HYPERSPACE", "GAME_OVER", "COMBAT")
DOCKED = ("LOCATION", "MARKET", "MISSIONS")
OVERLAYS = ("INVENTORY", "MESSAGES", "MISSION_LOG", "HELP", "EXCHANGE", "RADIO", "NOTEBOOK", "PRICELOG")


def available():
    return state.game_state not in NOT_HERE


# ---------------------------------------------------------------------------
# Building the list
# ---------------------------------------------------------------------------

def _base():
    """The game screen under any overlay (cargo, log...)."""
    gs = state.game_state
    if gs in OVERLAYS:
        return state.overlay_return or "SYSTEM"
    if gs == "GALAXY":
        return state.galaxy_return or "SYSTEM"
    return gs


def _item(label, key, action, *, here=False, enabled=True, note=""):
    return {"label": label, "key": key, "action": action, "here": here,
            "enabled": enabled, "note": note}


def build():
    """[(section title, [items])] for the current situation."""
    from core import events, travel
    gs = state.game_state
    base = _base()
    docked = base in DOCKED and state.current_location is not None
    sections = []

    # --- where you are ------------------------------------------------------
    if docked:
        loc = state.current_location
        price, cost = travel.refuel_cost()
        if price is None:
            fuel_note = "not sold here"
        elif state.fuel >= state.max_fuel - 0.01:
            fuel_note = "tank full"
        else:
            fuel_note = f"{cost:,} cr"
        sections.append((f"Docked at {loc.name}", [
            _item("Station menu", "", lambda: events.goto_station("LOCATION"),
                  here=gs == "LOCATION"),
            _item("Trading Post", "1", lambda: events.goto_station("MARKET"),
                  here=gs == "MARKET", enabled=bool(loc.market),
                  note="" if loc.market else "no market"),
            _item("Missions Board", "3", lambda: events.goto_station("MISSIONS"),
                  here=gs == "MISSIONS"),
            _item("Refuel", "5", events.quick_refuel, note=fuel_note,
                  enabled=price is not None and state.fuel < state.max_fuel - 0.01),
            _item("Undock", "ESC", events.undock),
        ]))

    # --- screens -------------------------------------------------------------
    sections.append(("Screens", [
        _item("Back to the ship" if not docked else "Back to the station",
              "", lambda: events.goto_screen(base), here=gs == base),
        _item("Galaxy chart", "M", lambda: events.goto_screen("GALAXY"), here=gs == "GALAXY"),
        _item("Cargo hold", "I", lambda: events.goto_screen("INVENTORY"), here=gs == "INVENTORY"),
        _item("Contracts", "P", lambda: events.goto_screen("MISSION_LOG"),
              here=gs == "MISSION_LOG",
              note=f"{sum(1 for m in state.missions if m.status == 'active')} active"),
        _item("Galactic Exchange", "E", lambda: events.goto_screen("EXCHANGE"), here=gs == "EXCHANGE"),
        _item("Comms log", "L", lambda: events.goto_screen("MESSAGES"), here=gs == "MESSAGES"),
        _item("Notebook", "J", lambda: events.goto_screen("NOTEBOOK"), here=gs == "NOTEBOOK"),
        _item("Price log", "K", lambda: events.goto_screen("PRICELOG"), here=gs == "PRICELOG",
              note=_pricelog_note()),
        _item("Radio", "O", lambda: events.goto_screen("RADIO"), here=gs == "RADIO",
              note=_radio_note()),
        _item("Pilot's Handbook", "H", lambda: events.goto_screen("HELP"), here=gs == "HELP"),
    ]))

    # --- fly somewhere in this system (only when not docked) -----------------
    system = state.current_system
    if not docked and system is not None:
        items = []
        px, py = state.system_player_x, state.system_player_y
        markets = [o for o in [*system.planets, *system.stations] if o.market]
        if markets:
            near = min(markets, key=lambda o: (o.x - px) ** 2 + (o.y - py) ** 2)
            items.append(_item(f"Nearest market: {near.name}", "",
                               lambda o=near: events.fly_to(o, "trade"), note="fly + trade"))
        for o in [*system.planets, *system.stations]:
            items.append(_item(o.name, "", lambda o=o: events.fly_to(o, "dock"),
                               note="fly + dock", here=(o.x, o.y) == (px, py)))
        for jp in system.jump_points:
            items.append(_item(f"Gate → {jp.destination}", "",
                               lambda jp=jp: events.fly_to(jp, "jump"),
                               note="jump menu" if travel.hard() else f"{travel.jump_fuel(jp)} fuel",
                               here=(jp.x, jp.y) == (px, py)))
        sections.append((f"Fly to (in {system.name})", items))
    return sections


def _pricelog_note():
    from core import pricelog
    rows = pricelog.summary()
    seen = sum(1 for r in rows if r[1] is not None)
    return f"{seen}/{len(rows)} goods" if seen else ""


def _radio_note():
    from core import audio
    from render.radio import title_artist
    path, _, _ = audio.now_playing()
    if path is None or audio.music_muted():
        return "off"
    name, _ = title_artist(path)
    return name if len(name) <= 16 else name[:15] + "."


def _flat():
    return [it for _, items in build() for it in items]


# ---------------------------------------------------------------------------
# Open / close / keys
# ---------------------------------------------------------------------------

def open_menu():
    state.quick_menu = True
    items = _flat()
    # start on the first useful row (not the screen you're already on)
    state.quick_index = next((i for i, it in enumerate(items)
                              if it["enabled"] and not it["here"]), 0)


def close():
    state.quick_menu = False


def handle(event):
    """Keys while the menu is open. Always consumes the key."""
    items = _flat()
    sym = event.sym
    if sym in (K.SPACE, K.ESCAPE, K.BACKSPACE):
        close()
        return
    if not items:
        return
    if sym in (K.UP, K.DOWN, K.TAB):
        step = -1 if sym == K.UP else 1
        for _ in range(len(items)):                 # skip disabled rows
            state.quick_index = (state.quick_index + step) % len(items)
            if items[state.quick_index]["enabled"]:
                break
        return
    if sym in (K.RETURN, K.KP_ENTER):
        _choose(items[state.quick_index % len(items)])
        return
    # the usual shortcut letters / numbers pick the matching row
    name = getattr(sym, "name", "")
    key = {"N1": "1", "N3": "3", "N5": "5"}.get(name, name if len(name) == 1 else None)
    for it in items:
        if key and it["key"] == key:
            _choose(it)
            return


def _choose(item):
    if not item["enabled"]:
        return
    close()
    item["action"]()
