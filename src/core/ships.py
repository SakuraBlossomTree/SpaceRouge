"""Ship classes for player and enemies."""

import random


class PlayerShip:
    """The player's ship with combat and travel stats."""

    def __init__(self):
        self.name = "Rogue"

        # Combat stats
        self.max_hull = 100
        self.hull = 100
        self.attack = 15
        self.defense = 5
        self.engine = 10          # affects escape chance

        # Travel
        self.max_fuel = 100
        self.fuel = 100

        # Temporary combat modifiers (reset each turn)
        self.defending = False

    def is_alive(self):
        return self.hull > 0

    def take_damage(self, amount):
        """Apply damage after defense, return actual damage dealt."""
        mitigation = self.defense * 2 if self.defending else self.defense
        actual = max(1, amount - mitigation)
        self.hull = max(0, self.hull - actual)
        return actual

    def reset_turn_modifiers(self):
        self.defending = False


class EnemyShip:
    """An enemy ship encountered in combat."""

    def __init__(self, name, hull, attack, defense, engine, loot_value):
        self.name = name
        self.max_hull = hull
        self.hull = hull
        self.attack = attack
        self.defense = defense
        self.engine = engine
        self.loot_value = loot_value

        self.defending = False

    def is_alive(self):
        return self.hull > 0

    def take_damage(self, amount):
        mitigation = self.defense * 2 if self.defending else self.defense
        actual = max(1, amount - mitigation)
        self.hull = max(0, self.hull - actual)
        return actual

    def reset_turn_modifiers(self):
        self.defending = False


# ---------------------------------------------------------------------------
# Pirate definitions — add more types here later without touching combat logic
# ---------------------------------------------------------------------------

PIRATE_TYPES = [
    {
        "name": "Raider",
        "hull": 40,
        "attack": 10,
        "defense": 2,
        "engine": 6,
        "loot_value": 20,
    },
    {
        "name": "Smuggler",
        "hull": 30,
        "attack": 8,
        "defense": 1,
        "engine": 12,   # faster, harder to escape from
        "loot_value": 30,
    },
    {
        "name": "Marauder",
        "hull": 60,
        "attack": 14,
        "defense": 5,
        "engine": 5,
        "loot_value": 50,
    },
]


def spawn_pirate():
    """Return a random EnemyShip from the pirate roster."""
    data = random.choice(PIRATE_TYPES)
    return EnemyShip(**data)
