from __future__ import annotations

import random


class Mission:
    def __init__(self, id, title, description, mission_type, reward_credits,
                 reward_items, status, source, destination, difficulty,
                 cargo=None, amount=None, systems_to_visit=None):
        self.id = id
        self.title = title
        self.mission_type = mission_type
        self.description = description
        self.reward_credits = reward_credits
        self.reward_items = reward_items
        self.status = status
        self.source = source
        self.destination = destination
        self.difficulty = difficulty
        self.cargo = cargo
        self.amount = amount
        self.systems_to_visit = systems_to_visit or []  # for patrol missions

    @property
    def is_selectable(self):
        return self.status in ("available", "active")


# --- Reward tables by difficulty ---------------------------------------------

REWARDS = {
    1: (100, 300),   # easy
    2: (300, 600),   # medium
    3: (600, 1000),  # hard
}

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

def generate_missions(location, current_system, all_stars, count=4):
    """
    Generate a pool of missions for a location.
    
    location       — the Planet or Station the player is visiting
    current_system — the StarSystem it belongs to
    all_stars      — full star list for picking destinations
    count          — how many missions to generate
    """
    archetype = getattr(current_system, "archetype", "Trade Hub")
    source_name = location.name
    missions = []

    # Pick other systems as potential destinations
    other_stars = [s for s in all_stars if s.name != current_system.name]
    if not other_stars:
        return missions

    weights = ARCHETYPE_WEIGHTS.get(archetype, ARCHETYPE_WEIGHTS["Trade Hub"])
    types   = list(weights.keys())
    w_vals  = list(weights.values())

    for _ in range(count):
        mission_type = random.choices(types, weights=w_vals, k=1)[0]
        difficulty   = random.randint(1, 3)
        r_min, r_max = REWARDS[difficulty]
        reward       = random.randint(r_min, r_max)

        dest_star    = random.choice(other_stars)
        dest_system  = dest_star.system
        dest_name    = (
            dest_system.planets[0].name if dest_system.planets
            else dest_system.stations[0].name if dest_system.stations
            else dest_star.name
        )

        if mission_type == "cargo":
            cargo_pool = ARCHETYPE_CARGO.get(archetype, ["Food"])
            commodity  = random.choice(cargo_pool)
            a_min, a_max = CARGO_AMOUNTS[difficulty]
            amount     = random.randint(a_min, a_max)
            title_t, desc_t = random.choice(CARGO_TEMPLATES)
            title = title_t
            desc  = desc_t.format(
                amount=amount,
                commodity=commodity,
                source=source_name,
                destination=dest_name,
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
                difficulty=difficulty,
            ))

        elif mission_type == "survey":
            title_t, desc_t = random.choice(SURVEY_TEMPLATES)
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
            patrol_stars = random.sample(
                other_stars, min(2, len(other_stars))
            )
            systems_to_visit = [s.name for s in patrol_stars]
            title_t, desc_t = random.choice(PATROL_TEMPLATES)
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
            title_t, desc_t = random.choice(BOUNTY_TEMPLATES)
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

    return missions