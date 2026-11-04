"""Getting around: flying inside a system, autopilot, and fuel.

Flying inside a system is free. Fuel is only burned by jump gates, and every
gate always costs the same: 3 + (distance between the stars) / 3, so a typical
jump is 7-10 fuel and a full tank lasts about a dozen jumps.

(The old Hard difficulty lives on in core/hard_mode.py.)
"""

import math
import time

from core import state
from core.world import FUEL_PRICES

def system_autopilot_line(obj):
    """Scanner line for a planet / station / gate in the system map: what
    flying there with autopilot takes. The autopilot moves one axis at a time,
    so the move count is the Manhattan distance."""
    moves = abs(obj.x - state.system_player_x) + abs(obj.y - state.system_player_y)
    if moves == 0:
        return "Autopilot: you are already here"
    days = (state.move_counter + moves) // MOVES_PER_DAY
    text = f"Autopilot: {moves} moves, no fuel"
    if days:
        text += f", {days} day{'s' if days != 1 else ''}"
    return text


MOVES_PER_DAY = 50         # every this many moves inside a system a day passes
AUTOPILOT_STEP = 0.03      # seconds per cell while the autopilot flies


# ---------------------------------------------------------------------------
# Fuel
# ---------------------------------------------------------------------------

def _star(name):
    return next((s for s in state.stars if s.name == name), None)


def jump_fuel(jp):
    """Fuel a jump gate needs (whole units, always the same for that gate)."""
    a, b = _star(jp.source), _star(jp.destination)
    if a is None or b is None:
        return 5
    return gate_fuel(a, b)


def gate_fuel(a, b):
    """Fuel for one jump gate between two star systems (easy-mode rule)."""
    return 3 + round(math.hypot(a.x - b.x, a.y - b.y) / 3)


def route_estimate(stars, here, there):
    """(jumps, fuel) for the fewest-jump gate route from system `here` to
    `there`, or None if unreachable."""
    by_name = {s.name: s for s in stars}
    if here not in by_name or there not in by_name:
        return None
    parent = {here: None}
    frontier = [here]
    while frontier and there not in parent:
        nxt = []
        for name in frontier:
            for jp in by_name[name].system.jump_points:
                if jp.destination in by_name and jp.destination not in parent:
                    parent[jp.destination] = name
                    nxt.append(jp.destination)
        frontier = nxt
    if there not in parent:
        return None
    path, cur = [], there
    while parent[cur] is not None:
        path.append((parent[cur], cur))
        cur = parent[cur]
    jumps = len(path)
    fuel = sum(gate_fuel(by_name[a], by_name[b]) for a, b in path)
    return jumps, fuel


def refuel_cost():
    """(price per unit, cost to fill up) here, or (None, 0) if no fuel is sold."""
    price = FUEL_PRICES.get(getattr(state.current_system, "archetype", None))
    if price is None:
        return None, 0
    return price, int(round((state.max_fuel - state.fuel) * price))


def check_stranded():
    """Game over only when there is truly no way out: no gate you have the
    fuel for, no fuel you can buy here, and no cargo left to sell for it."""
    system = state.current_system
    if system is None or state.game_state == "GAME_OVER":
        return False
    if any(state.fuel >= jump_fuel(jp) for jp in system.jump_points):
        return False
    if state.inventory.items:
        return False                          # sell cargo to pay for fuel
    price, _ = refuel_cost()
    if price is not None and system.jump_points:
        cheapest = min(jump_fuel(jp) for jp in system.jump_points)
        if state.credits >= (cheapest - state.fuel) * price:
            return False                      # can buy enough for one jump
    state.game_over_reason = ("Stranded: your tank is too low for any jump gate "
                              "and there's no fuel you can buy here.")
    state.game_state = "GAME_OVER"
    return True


# ---------------------------------------------------------------------------
# Flying
# ---------------------------------------------------------------------------

def step(dx, dy):
    """Move the ship one cell. Flying is free, but time still passes:
    MOVES_PER_DAY moves make a day (rent, prices and the economy move on)."""
    state.system_player_x += dx
    state.system_player_y += dy
    state.move_counter += 1
    if state.move_counter >= MOVES_PER_DAY:
        state.move_counter = 0
        from core.debt import advance_day, check_deadline
        advance_day()
        check_deadline()
    return True


def _targets():
    """Planets, stations and gates of this system, nearest to the ship first."""
    system = state.current_system
    if system is None:
        return []
    objs = [*system.planets, *system.stations, *system.jump_points]
    px, py = state.system_player_x, state.system_player_y
    return sorted(objs, key=lambda o: (o.x - px) ** 2 + (o.y - py) ** 2)


def _label(obj):
    if hasattr(obj, "destination"):
        return f"the gate to {obj.destination}"
    return obj.name


def start_autopilot(x, y, name):
    x, y = int(round(x)), int(round(y))
    if (x, y) == (state.system_player_x, state.system_player_y):
        return
    state.autopilot = (x, y, name)
    state.autopilot_then = None
    state.autopilot_next = time.time()
    state.add_message(f"Autopilot: flying to {name}.")


def autopilot_next_target(direction=1):
    """TAB: fly to the next planet / station / gate (Shift+TAB: previous).
    The list is in fixed map order so repeated TABs walk through all of them."""
    system = state.current_system
    if system is None:
        return
    objs = [*system.planets, *system.stations, *system.jump_points]
    if not objs:
        return
    if state.autopilot is None:
        # start from the object nearest the ship
        here = _targets()[0]
        if (here.x, here.y) == (state.system_player_x, state.system_player_y) and len(objs) > 1:
            i = objs.index(here) + direction
        else:
            i = objs.index(here)
    else:
        i = state.autopilot_index + direction
    i %= len(objs)
    state.autopilot_index = i
    target = objs[i]
    state.autopilot = None
    start_autopilot(target.x, target.y, _label(target))


def update_autopilot():
    """Called every frame: moves the ship one cell toward the target."""
    if state.autopilot is None:
        return
    if state.game_state != "SYSTEM":
        if state.game_state not in ("INVENTORY", "MESSAGES", "MISSION_LOG", "HELP", "EXCHANGE", "RADIO", "NOTEBOOK", "PRICELOG"):
            state.autopilot = None
        return
    now = time.time()
    if now < state.autopilot_next:
        return
    state.autopilot_next = now + AUTOPILOT_STEP
    tx, ty, name = state.autopilot
    dx, dy = tx - state.system_player_x, ty - state.system_player_y
    if dx == 0 and dy == 0:
        state.autopilot = None
        return
    # step along the longer axis first: a straight-ish line to the target
    if abs(dx) >= abs(dy):
        moved = step(1 if dx > 0 else -1, 0)
    else:
        moved = step(0, 1 if dy > 0 else -1)
    if not moved:
        state.autopilot = None
        return
    if (state.system_player_x, state.system_player_y) == (tx, ty):
        state.autopilot = None
        then, state.autopilot_then = state.autopilot_then, None
        if then is not None:
            from core import events
            events.arrive(*then)
            return
        system = state.current_system
        gate = any((jp.x, jp.y) == (tx, ty) for jp in system.jump_points)
        body = any((o.x, o.y) == (tx, ty) for o in [*system.planets, *system.stations])
        if gate:
            state.add_message(f"Arrived at {name}. ENTER for the jump menu.")
        elif body:
            state.add_message(f"Arrived at {name}. ENTER to dock.")
