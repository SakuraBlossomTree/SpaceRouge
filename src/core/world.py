"""World generation: star systems, planet surfaces, station hubs."""

import random

from core.entities import Star, StarSystem, Planet, Station, JumpPoint
from core.seedgen import SeedSequence, generate_food_price

WIDTH = 80
HEIGHT = 60

STAR_NAME_PREFIXES = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta",
    "Iota", "Kappa", "Lambda", "Mu", "Nu", "Xi", "Omicron", "Pi", "Rho",
    "Sigma", "Tau", "Upsilon", "Phi", "Chi", "Psi", "Omega",
]
 
STAR_NAME_SUFFIXES = [
    "Prime", "Minor", "Major", "Secundus", "Tertius", "IV", "V", "VI",
    "Reach", "Expanse", "Deep", "Drift", "Cross", "Point", "Gate",
]
 
PLANET_NAME_PARTS = [
    "Nova", "Kepler", "Rho", "Cygni", "Draconis", "Lyrae", "Aquilae",
    "Velorum", "Carinae", "Puppis", "Centauri", "Eridani", "Tauri",
    "Haven", "Refuge", "Bastion", "Frontier", "Outpost", "Verge", "Reach",
    "Arden", "Calyx", "Duren", "Eos", "Ferin", "Gorn", "Havel", "Irix",
]
 
STATION_NAME_PARTS = [
    "Orbital", "Station", "Depot", "Waypoint", "Platform", "Relay",
    "Outpost", "Hub", "Terminal", "Anchorage", "Port", "Nexus",
]

FACTIONS = [
    "United Nations",
    "Independent",
    "Free Traders Guild",
    "Outer Colonies",
    "Corporate Syndicate",
    "Frontier Alliance",
]

PLANET_COLORS = [
    (0, 0, 255),
    (255, 0, 0),
    (0, 255, 0),
    (255, 165, 0),
    (128, 0, 128),
    (0, 255, 255),
    (180, 180, 100),
]

STAR_TYPES = {
    "Red Dwarf": {
        "color": (255, 0, 0)
    },

    "Blue Dwarf": {
        "color": (0, 0, 255)
    },

    "White Dwarf": {
        "color": (255, 255, 255)
    },
    "Yellow Dwarf": {
        "color": (255, 255, 0)
    }
}

STAR_FRAMES = {
    "Red Dwarf": [
        ".",
        "*"
    ],

    "Yellow Dwarf": [
        "*",
        "o",
        "O",
        "o"
    ],

    "Blue Dwarf": [
        ".",
        "-",
        "*",
        "-"
    ],

    "White Dwarf": [
        "*",
        "O",
        "*"
    ]
}

# Reserved names that get hand-built systems
RESERVED = {"Sol", "Vega"}

# Total stars in the galaxy (including Sol and Vega)
GALAXY_SIZE = 30
 
# System-map bounds — objects placed within this area
SYS_W = 70
SYS_H = 50
SYS_MARGIN = 5

# --- Name generation ---------------------------------------------------------
 
def _gen_star_name(seq, used_names):
    """Generate a unique star name from the seed sequence."""
    for _ in range(100):
        prefix = STAR_NAME_PREFIXES[seq.next_seed() % len(STAR_NAME_PREFIXES)]
        suffix = STAR_NAME_SUFFIXES[seq.next_seed() % len(STAR_NAME_SUFFIXES)]
        name = f"{prefix} {suffix}"
        if name not in used_names and name not in RESERVED:
            used_names.add(name)
            return name
    # Fallback — shouldn't happen with 30 stars and this pool size yeah I think
    name = f"Star-{seq.next_seed() % 9999}"
    used_names.add(name)
    return name
 
 
def _gen_planet_name(seq):
    a = PLANET_NAME_PARTS[seq.next_seed() % len(PLANET_NAME_PARTS)]
    b = PLANET_NAME_PARTS[seq.next_seed() % len(PLANET_NAME_PARTS)]
    if a == b:
        return a
    return f"{a} {b}"
 
 
def _gen_station_name(system_name, seq):
    part = STATION_NAME_PARTS[seq.next_seed() % len(STATION_NAME_PARTS)]
    return f"{system_name} {part}"

def create_sol_system():
    ''' Sol Solar system generation'''
    system = StarSystem("Sol")

    system.planets.append(
        Planet(
            20,
            20,
            "Earth",
            "United Nations",
            12345,
            (0, 0, 255),
            {"Food": generate_food_price()},
        )
    )

    system.planets.append(
        Planet(
            30,
            25,
            "Mars",
            "United Nations",
            67890,
            (255, 0, 0),
            {"Food": generate_food_price(SeedSequence(67890))},
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Earth Orbital",
            "United Nations",
            {"Food": generate_food_price()},
        )
    )

    system.jump_points.append(
        JumpPoint(
            35,
            20,
            system.name + " jump point",
            system.name,
            "Vega",
            10,
        )
    )

    return system

def create_vega_system():

    system = StarSystem("Vega")

    system.planets.append(
        Planet(
            20,
            20,
            "New Horizon",
            "Independent",
            11111,
            (0, 0, 255),
            {"Food": generate_food_price()}
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Vega Prime",
            "Independent",
            {"Food": generate_food_price()}
        )
    )

    system.jump_points.append(
        JumpPoint(
            50,
            50,
            system.name + " jump point",
            system.name,
            "Sol",
            10,
        )
    )

    return system

# --- Procedural system generation --------------------------------------------
 
def _used_positions(system):
    """Return set of (x, y) already occupied in a system."""
    positions = set()
    for p in system.planets:
        positions.add((p.x, p.y))
    for s in system.stations:
        positions.add((s.x, s.y))
    for j in system.jump_points:
        positions.add((j.x, j.y))
    return positions
 
 
def _free_pos(seq, used):
    """Pick a random position not already in use."""
    for _ in range(200):
        x = SYS_MARGIN + seq.next_seed() % (SYS_W - SYS_MARGIN * 2)
        y = SYS_MARGIN + seq.next_seed() % (SYS_H - SYS_MARGIN * 2)
        if (x, y) not in used:
            used.add((x, y))
            return x, y
    # Fallback — extremely unlikely
    return SYS_MARGIN, SYS_MARGIN
 
 
def generate_system(name, master_seed):
    """Procedurally generate a full star system from a seed."""
    seq = SeedSequence(master_seed)
    system = StarSystem(name)
    used = _used_positions(system)
 
    num_planets  = 1 + seq.next_seed() % 3   # 1-3
    num_stations = seq.next_seed() % 3        # 0-2
 
    for i in range(num_planets):
        x, y = _free_pos(seq, used)
        planet_name = _gen_planet_name(seq)
        faction = FACTIONS[seq.next_seed() % len(FACTIONS)]
        color = PLANET_COLORS[seq.next_seed() % len(PLANET_COLORS)]
        planet_seed = seq.next_seed()
        food_price = generate_food_price(SeedSequence(planet_seed))
        system.planets.append(
            Planet(x, y, planet_name, faction, planet_seed, color,
                   {"Food": food_price})
        )
 
    for i in range(num_stations):
        x, y = _free_pos(seq, used)
        station_name = _gen_station_name(name, seq)
        faction = FACTIONS[seq.next_seed() % len(FACTIONS)]
        food_price = generate_food_price(SeedSequence(seq.next_seed()))
        system.stations.append(
            Station(x, y, station_name, faction, {"Food": food_price})
        )
 
    # Jump points are added later by _wire_jump_points
    return system
 
 
# --- Jump point wiring -------------------------------------------------------
 
def _wire_jump_points(stars, master_seq):
    """
    Randomly wire jump points between stars.
    Each star gets 1-3 outgoing connections to random other stars.
    Jump points are placed at random free positions in each system.
    """
    star_map = {star.name: star for star in stars}
 
    for star in stars:
        system = star.system
        used = _used_positions(system)
 
        num_jumps = 1 + master_seq.next_seed() % 3  # 1-3 jump points
 
        # Pick random destinations (no self-loops, no duplicates)
        existing_dests = {jp.destination for jp in system.jump_points}
        candidates = [s.name for s in stars if s.name != star.name and s.name not in existing_dests]
        master_seq.step()  # advance before slicing
        random.shuffle(candidates)
        destinations = candidates[:num_jumps]
 
        for dest in destinations:
            x, y = _free_pos(master_seq, used)
            cost = 10 + master_seq.next_seed() % 41  # 10-50 credits
            system.jump_points.append(
                JumpPoint(x, y, f"{star.name} -> {dest}", star.name, dest, cost)
            )

# --- Main entry point --------------------------------------------------------
 
def generate_stars():
    """Generate the full galaxy of 30 stars with procedural systems."""
    master_seq = SeedSequence()  # fixed galaxy seed — change to randomize
 
    # Step 1: generate star names and positions
    used_names = set(RESERVED)
    used_galaxy_pos = set()
    stars = []
 
    # Hand-built stars first so they claim their names
    for name in ("Sol", "Vega"):
        for _ in range(200):
            x = master_seq.next_seed() % WIDTH
            y = master_seq.next_seed() % HEIGHT
            if (x, y) not in used_galaxy_pos:
                used_galaxy_pos.add((x, y))
                break
        star_type = "Yellow Dwarf" if name == "Sol" else "Blue Dwarf"
        stars.append(Star(x, y, name, star_type))
 
    # Procedural stars
    for _ in range(GALAXY_SIZE - len(RESERVED)):
        name = _gen_star_name(master_seq, used_names)
        for _ in range(200):
            x = master_seq.next_seed() % WIDTH
            y = master_seq.next_seed() % HEIGHT
            if (x, y) not in used_galaxy_pos:
                used_galaxy_pos.add((x, y))
                break
        star_type = list(STAR_TYPES.keys())[master_seq.next_seed() % len(STAR_TYPES)]
        stars.append(Star(x, y, name, star_type))
 
    # Step 2: assign systems
    for star in stars:
        if star.name == "Sol":
            star.system = create_sol_system()
        elif star.name == "Vega":
            star.system = create_vega_system()
        else:
            star.system = generate_system(star.name, master_seq.next_seed())
 
    # Step 3: wire jump points across all systems
    _wire_jump_points(stars, master_seq)
 
    return stars


def generate_planet(seed):
    """Procedurally generate a planet surface tile map from a seed."""
    random.seed(seed)

    width = 80
    height = 50

    planet_map = []

    for y in range(height):
        row = []
        for x in range(width):
            roll = random.random()

            if roll < 0.15:
                row.append("^")
            elif roll < 0.35:
                row.append("~")
            else:
                row.append(".")

        planet_map.append(row)

    return planet_map


def generate_hub(seed):
    """Procedurally generate a station/planet hub map with buildings."""
    random.seed(seed)

    width = 20
    height = 12

    hub = []

    for y in range(height):
        row = []
        for x in range(width):
            if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                row.append("#")
            else:
                row.append(".")
        hub.append(row)

    buildings = ["T", "S", "E", "B"]

    for building in buildings:
        while True:
            x = random.randint(1, width - 2)
            y = random.randint(1, height - 2)

            if hub[y][x] == ".":
                hub[y][x] = building
                break

    return hub