"""Hull repairs at stations: pay credits, get hull points back.

Damage now carries between fights (core/encounter.py no longer patches you up
for free), so this is where the credits from trading go. Pure logic, no UI.
"""

from core import state

PRICE_PER_HULL = 2      # credits per hull point


def damage():
    ship = state.player_ship
    return max(0, ship.max_hull - ship.hull)


def cost(points=None):
    """Credits to repair `points` hull (default: all the damage)."""
    return (damage() if points is None else points) * PRICE_PER_HULL


def repair():
    """Repair as much as the player can pay for. Returns (points, credits)."""
    ship = state.player_ship
    points = min(damage(), state.credits // PRICE_PER_HULL)
    if points <= 0:
        return 0, 0
    paid = points * PRICE_PER_HULL
    state.credits -= paid
    ship.hull += points
    return points, paid
