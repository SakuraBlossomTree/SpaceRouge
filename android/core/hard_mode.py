"""ARCHIVED: the removed Hard difficulty.

Nothing imports this file. It keeps Hard mode's rules in one place so they can
be brought back. The original spec:

HARD  Every move inside a system burns about 1 fuel (a little more with cargo,
      a damaged hull or big debt, plus a small random variance), 50 moves make
      a day, and running dry is game over. Jump gates themselves need no fuel.
      Mission rewards were multiplied by 3.

To restore it you need to put these hooks back (the live code is Easy only):

  core/travel.py
    * DIFFICULTIES / DIFFICULTY_INFO / difficulty() / hard() / toggle_difficulty():
        the "difficulty" setting lives in settings.json via fonts.settings().
    * jump_fuel(jp):       `if hard(): return 0`   (gates are free on Hard)
    * check_stranded():    `... or hard()` in the early-return (no stranding on Hard)
    * step(dx, dy):        `if hard(): return hard_mode.step(dx, dy)`
    * system_autopilot_line(obj): Hard showed "~N fuel for M moves" using
        moves * hard_mode.move_fuel(variance=False)
  core/events.py
    * title screen: G / LEFT / RIGHT called travel.toggle_difficulty()
    * mission completion paid mission_reward(mission) (3x on Hard) in the payout
        and in the "Mission complete" message
  core/quickmenu.py: gate rows said "jump menu" on Hard instead of "N fuel"
  render/title.py: the Difficulty selector (EASY / HARD buttons + description)
  render/hud.py: Ship panel right_title "HARD"/"EASY"; fuel meter fmt "{:.1f}/{:.0f}"
  render/jumppoint.py: "Jump fuel: none (Hard: flying burns fuel)"
  render/missions.py, render/mission_log.py: displayed mission_reward(m)
  render/help.py: the Time / Fuel paragraphs about Hard
  core/tutorial.py: "(on Hard every move burns fuel)"
  core/state.py: move_counter (already kept) counts moves toward the next day.
"""

import random

from core import state

DIFFICULTIES = ("easy", "hard")
DIFFICULTY_INFO = {
    "easy": "Flying is free; only jump gates burn fuel.",
    "hard": "Every move burns fuel; 50 moves make a day.",
}

HARD_REWARD_MULTIPLIER = 3.0     # mission rewards
MOVES_PER_DAY = 50

# Fuel per move
FUEL_PER_CARGO_ITEM = 0.03       # each unit in the hold
FUEL_PER_HULL_DAMAGE = 0.1       # at 0% hull; scales with the damage taken
FUEL_DEBT_FACTOR = 1.05          # worn engines when debt is above DEBT_ENGINE_LIMIT
DEBT_ENGINE_LIMIT = 5000
FUEL_VARIANCE = 0.2              # +/- random wobble per move


def mission_reward(mission):
    """Credits a contract pays on Hard."""
    return int(round(mission.reward_credits * HARD_REWARD_MULTIPLIER))


def move_fuel(variance=True):
    """Fuel for one move."""
    cost = 1.0
    cost += len(state.inventory.items) * FUEL_PER_CARGO_ITEM       # heavy hold
    cost += (1.0 - state.player_ship.hull / state.player_ship.max_hull) * FUEL_PER_HULL_DAMAGE
    if variance:
        cost += random.uniform(-FUEL_VARIANCE, FUEL_VARIANCE)
    if state.debt > DEBT_ENGINE_LIMIT:                             # worn engines
        cost *= FUEL_DEBT_FACTOR
    return max(0.5, cost)


def system_autopilot_line(obj):
    """Scanner line for an object in the system map (autopilot moves one axis
    at a time, so the move count is the Manhattan distance)."""
    moves = abs(obj.x - state.system_player_x) + abs(obj.y - state.system_player_y)
    if moves == 0:
        return "Autopilot: you are already here"
    fuel = moves * move_fuel(variance=False)
    return f"Autopilot: ~{fuel:.0f} fuel for {moves} moves"


def step(dx, dy):
    """Move the ship one cell. Burns fuel, MOVES_PER_DAY moves make a day, and
    running out is game over. Returns False if the ship couldn't move."""
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
    if state.move_counter >= MOVES_PER_DAY:
        state.move_counter = 0
        from core.debt import advance_day
        advance_day()
    return True
