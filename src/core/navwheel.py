"""Autopilot wheel (TAB in a system): a radial menu of every planet, station
and jump gate, so you can pick where to fly without cycling one by one.

    TAB / → / ↓ / D     next place          Shift+TAB / ← / ↑ / A   previous
    1-9                 pick a place directly
    ENTER               fly there (docks / opens the jump menu on arrival)
    F                   fly there and stop (no docking)
    ESC / TAB twice     close

Places sit around the wheel in map order, nearest-first starting at the top.
"""

import math
import time

import tcod

from core import state

K = tcod.event.KeySym

NUMBER_KEYS = {}
for _d in range(1, 10):
    for _p in ("N", "KP_"):
        _k = getattr(K, f"{_p}{_d}", None)
        if _k is not None:
            NUMBER_KEYS[_k] = _d - 1


def available():
    return state.game_state == "SYSTEM" and state.current_system is not None


def places():
    """[(kind, obj, label, distance)] in wheel order: nearest first."""
    system = state.current_system
    if system is None:
        return []
    px, py = state.system_player_x, state.system_player_y
    out = []
    for kind, objs in (("planet", system.planets), ("station", system.stations),
                       ("gate", system.jump_points)):
        for o in objs:
            label = f"Gate: {o.destination}" if kind == "gate" else o.name
            out.append((kind, o, label, abs(o.x - px) + abs(o.y - py)))
    out.sort(key=lambda p: p[3])
    return out


def open_wheel():
    items = places()
    if not items:
        state.add_message("Nothing to fly to in this system.")
        return
    state.nav_wheel = True
    state.nav_wheel_opened = time.time()
    # start on the closest place you are not already sitting on
    state.nav_wheel_index = next((i for i, p in enumerate(items) if p[3] > 0), 0)


def close():
    state.nav_wheel = False


def _go(item, dock):
    from core import events, travel
    kind, obj = item[0], item[1]
    close()
    if dock:
        events.fly_to(obj, "jump" if kind == "gate" else "dock")
    else:
        if (obj.x, obj.y) == (state.system_player_x, state.system_player_y):
            return
        name = f"the gate to {obj.destination}" if kind == "gate" else obj.name
        travel.start_autopilot(obj.x, obj.y, name)


def handle(event):
    """Keys while the wheel is open. Always consumes the key."""
    items = places()
    sym = event.sym
    if not available() or not items:
        close()
        return
    n = len(items)
    shift = bool(getattr(event, "mod", 0) & tcod.event.Modifier.SHIFT)
    if sym in (K.ESCAPE, K.BACKSPACE):
        close()
    elif sym == K.TAB and not shift:
        state.nav_wheel_index = (state.nav_wheel_index + 1) % n
    elif sym == K.TAB or sym in (K.LEFT, K.UP, K.A, K.W):
        state.nav_wheel_index = (state.nav_wheel_index - 1) % n
    elif sym in (K.RIGHT, K.DOWN, K.D, K.S):
        state.nav_wheel_index = (state.nav_wheel_index + 1) % n
    elif sym in NUMBER_KEYS:
        if NUMBER_KEYS[sym] < n:
            state.nav_wheel_index = NUMBER_KEYS[sym]
    elif sym in (K.RETURN, K.KP_ENTER):
        _go(items[state.nav_wheel_index % n], dock=True)
    elif sym == K.F:
        _go(items[state.nav_wheel_index % n], dock=False)


def angle(i, n):
    """Angle of slot i of n (radians): slot 0 at the top, clockwise."""
    return -math.pi / 2 + 2 * math.pi * i / max(1, n)
