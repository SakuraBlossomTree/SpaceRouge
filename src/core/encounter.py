"""Encounter trigger logic.

Checks whether a combat encounter should fire when the player
arrives at a destination or jumps between star systems.
"""

import random

from core import state
from core.combat import CombatManager
from core.ships import spawn_pirate

# Chance of a pirate encounter per trigger event
SYSTEM_ARRIVAL_CHANCE = 0.4   # arriving at a planet/station
JUMP_CHANCE           = 0.3   # jumping between star systems


def roll_encounter(chance, player_ship):
    """
    Roll for a combat encounter.
    Returns a CombatManager if an encounter triggers, otherwise None.
    """
    if state.tutorial_run:
        return None          # the practice galaxy is pirate-free
    if random.random() < chance:
        pirate = spawn_pirate()
        return CombatManager(player_ship, pirate)
    return None


def check_arrival(player_ship):
    """Call when player arrives at a planet or station."""
    return roll_encounter(SYSTEM_ARRIVAL_CHANCE, player_ship)


# Chance of an ambush when you arrive in a system after a jump, by the
# destination's archetype (the old flat JUMP_CHANCE is the fallback).
ARCHETYPE_JUMP_CHANCE = {
    "Trade Hub":    0.06,    # busy, well patrolled lanes
    "Military":     0.04,    # pirates keep away
    "Agricultural": 0.10,
    "Industrial":   0.10,
    "Research":     0.10,
    "Mining":       0.15,    # lonely belts, rich cargo
    "Frontier":     0.25,    # nobody is watching
}
DEFAULT_JUMP_CHANCE = 0.12
RAID_BONUS = 0.25            # added while the economy reports pirates on this route

# What losing a fight costs (hull never stays at 0: you limp away)
PLUNDER_SHARE = 0.25         # share of your credits the pirates take
DEFEAT_HULL_SHARE = 0.20     # hull left after a defeat, as a share of max hull


def jump_chance(origin, destination, archetype=None):
    """Ambush chance for a jump origin -> destination (system names)."""
    chance = ARCHETYPE_JUMP_CHANCE.get(archetype, DEFAULT_JUMP_CHANCE)
    eco = state.economy
    if eco is not None and origin and destination and eco.route_raided(origin, destination):
        chance += RAID_BONUS
    return chance


def check_jump(player_ship, origin=None, destination=None, archetype=None):
    """Call when player jumps between star systems. With the route's system
    names the chance depends on where you arrive and on active raids."""
    if origin is None and destination is None:
        return roll_encounter(JUMP_CHANCE, player_ship)
    return roll_encounter(jump_chance(origin, destination, archetype), player_ship)


def apply_defeat(player_ship):
    """Pirates win but leave you flying. Returns the credits they took."""
    lost = int(state.credits * PLUNDER_SHARE)
    state.credits -= lost
    player_ship.hull = max(1, int(player_ship.max_hull * DEFEAT_HULL_SHARE))
    return lost
