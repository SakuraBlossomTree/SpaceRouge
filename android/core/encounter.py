"""Encounter trigger logic.

Checks whether a combat encounter should fire when the player
arrives at a destination or jumps between star systems.
"""

import random

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
    if random.random() < chance:
        pirate = spawn_pirate()
        return CombatManager(player_ship, pirate)
    return None


def check_arrival(player_ship):
    """Call when player arrives at a planet or station."""
    return roll_encounter(SYSTEM_ARRIVAL_CHANCE, player_ship)


def check_jump(player_ship):
    """Call when player jumps between star systems."""
    return roll_encounter(JUMP_CHANCE, player_ship)
