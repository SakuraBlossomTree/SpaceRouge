"""Getting around: flying inside a system, autopilot, and fuel.

Two difficulties (chosen on the title screen, G):

EASY  Flying inside a system is free. Fuel is only burned by jump gates, and
      every gate always costs the same: 3 + (distance between the stars) / 3,
      so a typical jump is 7-10 fuel and a full tank lasts about a dozen jumps.

HARD  The original rules: every move burns about 1 fuel (more with cargo, a
      damaged hull, in dense systems or with big debt, plus a little random
      variance), 50 moves make a day, and running dry is game over. Jumps
      themselves need no fuel.
"""

import math
import random
import time

from core import state, fonts
from core.world import FUEL_PRICES, FUEL_CONSUMPTION_MODIFIERS

DIFFICULTIES = ("easy", "hard")
DIFFICULTY_INFO = {
    "easy": "Flying is free; only jump gates burn fuel.",
    "hard": "Every move burns fuel; 50 moves make a day.",
}


def difficulty():
    d = fonts.settings().get("difficulty", "easy")
    return d if d in DIFFICULTIES else "easy"


def hard():
    return difficulty() == "hard"


def toggle_difficulty():
    fonts.settings()["difficulty"] = "easy" if hard() else "hard"
    fonts.save_settings()
    return difficulty()

AUTOPILOT_STEP = 0.03      # seconds per cell while the autopilot flies


# ---------------------------------------------------------------------------
# Fuel
# ---------------------------------------------------------------------------

def _star(name):
    return next((s for s in state.stars if s.name == name), None)


def jump_fuel(jp):
    """Fuel a jump gate needs (whole units, always the same for that gate).
    Hard mode: none - fuel is burned flying instead."""
    if hard():
        return 0
    a, b = _star(jp.source), _star(jp.destination)
    if a is None or b is None:
        return 5
    return 3 + round(math.hypot(a.x - b.x, a.y - b.y) / 3)


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
    if system is None or state.game_state == "GAME_OVER" or hard():
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

def move_fuel():
    """Hard mode: fuel for one move (the original formula)."""
    cost = 1.0
    cost += len(state.inventory.items) * 0.15                     # heavy hold
    cost += (1.0 - state.player_ship.hull / state.player_ship.max_hull) * 0.3   # damage
    cost += random.uniform(-0.2, 0.2)                              # variance
    archetype = getattr(state.current_system, "archetype", None)
    cost *= FUEL_CONSUMPTION_MODIFIERS.get(archetype, 1.0)         # local conditions
    if state.debt > 5000:                                          # worn engines
        cost *= 1.1
    return max(0.5, cost)


def step(dx, dy):
    """Move the ship one cell. Easy: free. Hard: burns fuel, 50 moves = 1 day,
    and running out is game over. Returns False if the ship couldn't move."""
    if not hard():
        state.system_player_x += dx
        state.system_player_y += dy
        return True
    cost = move_fuel()
    if state.fuel <= 0 or state.fuel < cost:
        state.add_message("No fuel!" if state.fuel <= 0 else
                          f"Need {cost:.1f} fuel, only {state.fuel:.1f} remaining!")
        state.autopilot = None
        state.game_over_reason = "You ran out of fuel and drifted into the void."
        state.game_state = "GAME_OVER"
        return False
    state.system_player_x += dx
    state.system_player_y += dy
    state.fuel -= cost
    state.move_counter += 1
    if state.autopilot is None and abs(cost - 1.0) > 1e-9:
        state.add_message(f"Fuel used: {cost:.1f}")     # (not every autopilot step)
    if state.move_counter >= 50:
        state.move_counter = 0
        from core.debt import advance_day
        advance_day()
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
