"""Shipyard: simple permanent ship upgrades, bought with credits.

Each upgrade has one or more levels: (price, what it does). Levels are bought
in order. State lives in state.upgrades ({id: level}); the Market Scanner is
(the Market Scanner is fitted free from the start; Exchange Range extends it).
"""

from core import state

# (id, name, [(price, description), ...])
UPGRADES = [
    ("cargo", "Cargo Hold",
     [(1200, "+10 cargo space"), (3000, "+10 cargo space"), (7000, "+10 cargo space")]),
    ("fuel", "Fuel Tank",
     [(500, "+50 fuel capacity"), (1400, "+50 fuel capacity")]),
    ("hull", "Hull Plating",
     [(700, "+25 max hull"), (1800, "+25 max hull")]),
    ("scanrange", "Exchange Range",
     [(1800, "The Galactic Exchange scans markets 2 jumps out"),
      (4500, "The Galactic Exchange scans markets 3 jumps out"),
      (10000, "The Galactic Exchange scans markets 4 jumps out")]),
    ("jumprange", "Star Jump Scanner",
     [(1500, "Galaxy chart shows jump links 2 jumps out"),
      (4000, "Galaxy chart shows jump links 3 jumps out"),
      (9000, "Galaxy chart shows jump links 4 jumps out")]),
]

BASE_EXCHANGE_DEPTH = 1  # jumps of markets the Exchange scans, before upgrades
BASE_JUMP_VIEW = 1     # jumps of links the galaxy chart draws from your system, before upgrades

_BY_ID = {u[0]: u for u in UPGRADES}


def level(uid):
    return state.upgrades.get(uid, 0)


def jump_view_range():
    """How many jumps of gate links the galaxy chart draws from your system."""
    return BASE_JUMP_VIEW + state.upgrades.get("jumprange", 0)


def exchange_depth():
    """How many jumps of markets the Galactic Exchange scans."""
    return BASE_EXCHANGE_DEPTH + state.upgrades.get("scanrange", 0)


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
        "scanrange": f"{exchange_depth()} jump{'s' if exchange_depth() != 1 else ''}",
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
