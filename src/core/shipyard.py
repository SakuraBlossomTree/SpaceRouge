"""Shipyard: simple permanent ship upgrades, bought with credits.

Each upgrade has one or more levels: (price, what it does). Levels are bought
in order. State lives in state.upgrades ({id: level}).  The Long-Range System
Scanner is fitted free at level 0 (one jump); its upgrade levels extend the
range using the central values in core.scanner.
"""

from core import scanner, state

# (id, name, [(price, description), ...])
UPGRADES = [
    ("cargo", "Cargo Hold",
     [(1200, "+10 cargo space"), (3000, "+10 cargo space"), (7000, "+10 cargo space")]),
    ("fuel", "Fuel Tank",
     [(500, "+50 fuel capacity"), (1400, "+50 fuel capacity")]),
    ("hull", "Hull Plating",
     [(700, "+25 max hull"), (1800, "+25 max hull")]),
    ("scanrange", "Long-Range System Scanner",
     [(1800, f"{scanner.LEVEL_NAMES[1]} scanner: market intelligence "
              f"{scanner.RADII[1]} jumps out"),
      (4500, f"{scanner.LEVEL_NAMES[2]} scanner: market intelligence "
              f"{scanner.RADII[2]} jumps out"),
      (10000, f"{scanner.LEVEL_NAMES[3]} scanner: market intelligence "
               f"{scanner.RADII[3]} jumps out")]),
    ("jumprange", "Star Jump Scanner",
     [(1500, "Galaxy chart shows jump links 2 jumps out"),
      (4000, "Galaxy chart shows jump links 3 jumps out"),
      (9000, "Galaxy chart shows jump links 4 jumps out")]),
]

BASE_EXCHANGE_DEPTH = scanner.RADII[0]  # standard scanner range, before upgrades
BASE_JUMP_VIEW = 1     # jumps of links the galaxy chart draws from your system, before upgrades

_BY_ID = {u[0]: u for u in UPGRADES}


def level(uid):
    return state.upgrades.get(uid, 0)


def jump_view_range():
    """How many jumps of gate links the galaxy chart draws from your system."""
    return BASE_JUMP_VIEW + state.upgrades.get("jumprange", 0)


def exchange_depth():
    """How many jumps of markets the Long-Range System Scanner reaches."""
    return scanner.radius()


def levels(uid):
    return _BY_ID[uid][2]


def next_offer(uid):
    """(price, description) of the next level, or None when fully upgraded."""
    lv = level(uid)
    offers = levels(uid)
    return offers[lv] if lv < len(offers) else None


def current_text(uid):
    ship = state.player_ship
    return {
        "cargo": f"{state.inventory.space} units",
        "fuel": f"{state.max_fuel:.0f} fuel",
        "hull": f"{ship.max_hull} hull",
        "scanrange": f"{scanner.range_text()} · {scanner.level_name()} scanner",
        "jumprange": f"{jump_view_range()} jump{'s' if jump_view_range() != 1 else ''}",
    }[uid]


def available_count():
    """How many upgrades still have a level to buy."""
    return sum(1 for uid, _, offers in UPGRADES if level(uid) < len(offers))


def _apply(uid):
    if uid == "cargo":
        state.inventory.space += 10
    elif uid == "fuel":
        state.max_fuel += 50
    elif uid == "hull":
        state.player_ship.max_hull += 25
        state.player_ship.hull += 25
    # "jumprange" and "scanrange" need nothing here: their ranges read the level


def buy(uid):
    """Buy the next level. Returns (success, message)."""
    name = _BY_ID[uid][1]
    offer = next_offer(uid)
    if offer is None:
        return False, f"{name} is already fully upgraded."
    price, desc = offer
    if state.credits < price:
        return False, f"Not enough credits for {name}: it costs {price}."
    state.credits -= price
    state.upgrades[uid] = level(uid) + 1
    _apply(uid)
    return True, f"Fitted {name}: {desc}. (-{price} cr)"
