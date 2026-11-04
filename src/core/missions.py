from __future__ import annotations

import random
import zlib

from core import state
from core.seedgen import SeedSequence

class Mission:
    def __init__(self, id, title, description, mission_type, reward_credits,
                 reward_items, status, source, destination, difficulty,
                 cargo=None, amount=None, systems_to_visit=None, dest_system=None,
                 source_system=None, key=None):
        self.id = id
        self.source_system = source_system   # system the mission was posted in
        self.key = key                       # stable across regeneration
        self.day = None                      # in-game day this board was posted
        self.title = title
        self.mission_type = mission_type
        self.description = description
        self.reward_credits = reward_credits
        self.reward_items = reward_items
        self.status = status
        self.source = source
        self.destination = destination
        self.dest_system = dest_system
        self.difficulty = difficulty
        self.cargo = cargo
        self.amount = amount
        self.systems_to_visit = systems_to_visit or []  # for patrol missions

    @property
    def is_selectable(self):
        return self.status in ("available", "active")


# --- Reward tables by difficulty ---------------------------------------------

REWARDS = {
    1: (130, 400),   # easy
    2: (400, 800),   # medium
    3: (800, 1300),  # hard
}

# Extra pay on top of the difficulty roll
REWARD_PER_JUMP = {1: 50, 2: 70, 3: 90}   # per gate jump, by difficulty
MAX_JUMPS = {1: 3, 2: 6, 3: 99}           # how far a contract of each difficulty may send you
CARGO_VALUE_SHARE = 0.5   # share of the cargo's base market value

# --- Cargo amounts by difficulty ---------------------------------------------

CARGO_AMOUNTS = {
    1: (1, 3),
    2: (3, 6),
    3: (6, 10),
}

# --- Mission templates by type -----------------------------------------------

# Each template is (title, description) with {commodity}, {amount},
# {source}, {destination} as placeholders

CARGO_TEMPLATES = [
    (
        "Supply Run",
        "Deliver {amount} units of {commodity} from {source} to {destination}.",
    ),
    (
        "Urgent Delivery",
        "A shipment of {amount} units of {commodity} is desperately needed at {destination}.",
    ),
    (
        "Trade Contract",
        "Transport {amount} units of {commodity} to {destination} on behalf of a local merchant.",
    ),
]

SURVEY_TEMPLATES = [
    (
        "Survey Mission",
        "Fly to {destination} and perform a survey scan of the system.",
    ),
    (
        "Exploration Contract",
        "A research group needs data from {destination}. Travel there to collect it.",
    ),
]

PATROL_TEMPLATES = [
    (
        "Patrol Route",
        "Patrol the systems along a designated route and report back to {source}.",
    ),
    (
        "Security Detail",
        "Escort a patrol through nearby systems and return to {source}.",
    ),
]

BOUNTY_TEMPLATES = [
    (
        "Bounty: Wanted Pilot",
        "A wanted criminal was last spotted near {destination}. Track them down.",
    ),
    (
        "Bounty: Pirate Cell",
        "Intel suggests a pirate cell is operating out of {destination}. Investigate.",
    ),
]

# --- Archetype mission weights -----------------------------------------------
# Which mission types are more likely to appear at each archetype
# Format: {mission_type: weight}

ARCHETYPE_WEIGHTS = {
    "Agricultural": {"cargo": 6, "survey": 2, "patrol": 1, "bounty": 1},
    "Mining":       {"cargo": 5, "survey": 3, "patrol": 1, "bounty": 1},
    "Industrial":   {"cargo": 4, "survey": 2, "patrol": 2, "bounty": 2},
    "Trade Hub":    {"cargo": 4, "survey": 2, "patrol": 2, "bounty": 2},
    "Research":     {"cargo": 2, "survey": 6, "patrol": 1, "bounty": 1},
    "Frontier":     {"cargo": 3, "survey": 4, "patrol": 2, "bounty": 1},
    "Military":     {"cargo": 1, "survey": 1, "patrol": 5, "bounty": 3},
}

# Commodities each archetype is likely to send as cargo
ARCHETYPE_CARGO = {
    "Agricultural": ["Food", "Water"],
    "Mining":       ["Ore", "Rare Minerals"],
    "Industrial":   ["Machinery", "Electronics"],
    "Trade Hub":    ["Food", "Machinery", "Electronics", "Luxury Goods"],
    "Research":     ["Electronics", "Medicine"],
    "Frontier":     ["Food", "Medicine", "Water"],
    "Military":     ["Machinery", "Medicine"],
}


# --- ID counter --------------------------------------------------------------

_mission_counter = 0

def _next_id():
    global _mission_counter
    _mission_counter += 1
    return f"PROC-{_mission_counter:04d}"


# --- Core generator ----------------------------------------------------------

def generate_missions(location, current_system, all_stars, count=4, completed=(), day=0):
    """
    Generate a pool of missions for a location.
    
    location       — the Planet or Station the player is visiting
    current_system — the StarSystem it belongs to
    all_stars      — full star list for picking destinations
    count          — how many missions to generate
    """
    # zlib.crc32 is stable between runs (Python's hash() of a str is not),
    # so the same galaxy seed always posts the same contracts at a station
    # the day is part of the seed: a station posts a fresh board every day
    key = zlib.crc32((f"{location.name}|{current_system.name}|{day}").encode("utf-8"))
    seed = (state.galaxy_seed ^ key) % (2**32)
    seq = SeedSequence(seed)
    rng = random.Random(seed)

    archetype = getattr(current_system, "archetype", "Trade Hub")
    source_name = location.name
    missions = []

    # Pick other systems as potential destinations
    other_stars = [s for s in all_stars if s.name != current_system.name]
    if not other_stars:
        return missions

    # gate jumps from here to every other system (fewest-jump route)
    from core import travel
    dist = {}
    for s_ in other_stars:
        est = travel.route_estimate(all_stars, current_system.name, s_.name)
        dist[s_.name] = est[0] if est else 99

    weights = ARCHETYPE_WEIGHTS.get(archetype, ARCHETYPE_WEIGHTS["Trade Hub"])
    types   = list(weights.keys())
    w_vals  = list(weights.values())

    for i in range(count):
        # use seq instead of random
        # mission_type = types[seq.next_seed() % len(types)]  # no weights but consistent
        mission_type = "cargo"
        difficulty = 1 + seq.next_seed() % 3
        r_min, r_max = REWARDS[difficulty]
        reward = r_min + seq.next_seed() % (r_max - r_min)

        pool = [s_ for s_ in other_stars if dist[s_.name] <= MAX_JUMPS[difficulty]]
        if not pool:   # tiny/sparse galaxy: fall back to the nearest systems
            pool = sorted(other_stars, key=lambda s_: dist[s_.name])[:3]
        dest_star = pool[seq.next_seed() % len(pool)]
        dest_system  = dest_star.system
        dest_name    = (
            dest_system.planets[0].name if dest_system.planets
            else dest_system.stations[0].name if dest_system.stations
            else dest_star.name
        )

        if mission_type == "cargo":
            cargo_pool = ARCHETYPE_CARGO.get(archetype, ["Food"])
            commodity  = rng.choice(cargo_pool)
            a_min, a_max = CARGO_AMOUNTS[difficulty]
            amount     = rng.randint(a_min, a_max)
            # farther deliveries and pricier cargo pay more (no RNG used here)
            from core.world import BASE_PRICES
            jumps = min(dist[dest_star.name], 99)
            reward += REWARD_PER_JUMP[difficulty] * jumps
            reward += int(CARGO_VALUE_SHARE * amount * BASE_PRICES.get(commodity, 0))
            reward = int(round(reward / 5.0)) * 5
            title_t, desc_t = rng.choice(CARGO_TEMPLATES)
            title = title_t
            desc  = desc_t.format(
                amount=amount,
                commodity=commodity,
                source=source_name,
                destination=dest_name,
                dest_system=dest_star.name
            )
            missions.append(Mission(
                id=_next_id(),
                title=title,
                description=desc,
                mission_type="cargo",
                cargo=commodity,
                amount=amount,
                reward_credits=reward,
                reward_items=[],
                status="available",
                source=source_name,
                destination=dest_name,
                dest_system=dest_star.name,
                difficulty=difficulty,
                source_system=current_system.name,
            ))

        elif mission_type == "survey":
            title_t, desc_t = rng.choice(SURVEY_TEMPLATES)
            desc = desc_t.format(destination=dest_star.name, source=source_name)
            missions.append(Mission(
                id=_next_id(),
                title=title_t,
                description=desc,
                mission_type="survey",
                reward_credits=reward,
                reward_items=[],
                status="available",
                source=source_name,
                destination=dest_star.name,
                difficulty=difficulty,
            ))

        elif mission_type == "patrol":
            # Pick 2 intermediate systems to visit
            patrol_stars = rng.sample(
                other_stars, min(2, len(other_stars))
            )
            systems_to_visit = [s.name for s in patrol_stars]
            title_t, desc_t = rng.choice(PATROL_TEMPLATES)
            desc = desc_t.format(source=source_name, destination=source_name)
            missions.append(Mission(
                id=_next_id(),
                title=title_t,
                description=desc,
                mission_type="patrol",
                reward_credits=reward,
                reward_items=[],
                status="available",
                source=source_name,
                destination=source_name,  # return to source
                difficulty=difficulty,
                systems_to_visit=systems_to_visit,
            ))

        elif mission_type == "bounty":
            title_t, desc_t = rng.choice(BOUNTY_TEMPLATES)
            desc = desc_t.format(destination=dest_star.name, source=source_name)
            missions.append(Mission(
                id=_next_id(),
                title=title_t,
                description=desc,
                mission_type="bounty",
                reward_credits=reward,
                reward_items=[],
                status="available",
                source=source_name,
                destination=dest_star.name,
                difficulty=difficulty,
            ))

    # Keys are stable (same place, same slot), so a contract the player has
    # already finished is never posted again.
    for idx, m in enumerate(missions):
        m.key = f"{location.name}|{current_system.name}|{day}|{idx}"
        m.day = day
    return [m for m in missions if m.key not in completed]