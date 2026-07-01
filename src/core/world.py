"""World generation: star systems, planet surfaces, station hubs."""

import random

from core.entities import Star, StarSystem, Planet, Station, JumpPoint
from core.seedgen import SeedSequence, generate_food_price

WIDTH = 80
HEIGHT = 60

COMMODITIES = [
    "Food",
    "Water",
    "Ore",
    "Rare Minerals",
    "Machinery",
    "Medicine",
    "Electronics",
    "Luxury Goods",
]

# Base price for each commodity before archetype modifiers
BASE_PRICES = {
    "Food":          10,
    "Water":         8,
    "Ore":           15,
    "Rare Minerals": 40,
    "Machinery":     30,
    "Medicine":      25,
    "Electronics":   35,
    "Luxury Goods":  50,
}

# --- Archetypes --------------------------------------------------------------
# exports  → produced here, sold cheap (0.6x base price)
# imports  → needed here, bought expensive (1.5x base price)
# neutral  → available at base price
# Military systems have no market at all
 
ARCHETYPES = {
    "Agricultural": {
        "description": "Vast farmlands and food processing facilities.",
        "exports":  ["Food", "Water"],
        "imports":  ["Machinery", "Electronics"],
        "planets":  (2, 3),   # min, max planets
        "stations": (0, 2),
        "station_type": "Market",
    },
    "Mining": {
        "description": "Rich asteroid belts and deep-core extraction operations.",
        "exports":  ["Ore", "Rare Minerals"],
        "imports":  ["Food", "Machinery"],
        "planets":  (1, 2),
        "stations": (1, 2),
        "station_type": "Depot",
    },
    "Industrial": {
        "description": "Heavy manufacturing and shipbuilding complexes.",
        "exports":  ["Machinery", "Electronics"],
        "imports":  ["Ore", "Food"],
        "planets":  (1, 2),
        "stations": (1, 3),
        "station_type": "Hub",
    },
    "Trade Hub": {
        "description": "A bustling center of commerce connecting nearby systems.",
        "exports":  [],
        "imports":  [],
        "planets":  (1, 2),
        "stations": (2, 3),
        "station_type": "Hub",
    },
    "Research": {
        "description": "Cutting-edge laboratories and experimental facilities.",
        "exports":  ["Electronics", "Medicine"],
        "imports":  ["Food", "Rare Minerals"],
        "planets":  (1, 2),
        "stations": (1, 2),
        "station_type": "Outpost",
    },
    "Frontier": {
        "description": "A remote and underdeveloped system on the edge of known space.",
        "exports":  [],
        "imports":  ["Food", "Medicine", "Machinery"],
        "planets":  (1, 3),
        "stations": (0, 1),
        "station_type": "Outpost",
    },
    "Military": {
        "description": "A heavily fortified system with restricted civilian access.",
        "exports":  [],
        "imports":  [],
        "planets":  (1, 2),
        "stations": (1, 2),
        "station_type": "Outpost",
        "no_market": True,
    },
}
 
ARCHETYPE_NAMES = list(ARCHETYPES.keys())

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

# Reserved names that get hand-built systems
RESERVED = {"Sol", "Vega"}

# Total stars in the galaxy (including Sol and Vega)
GALAXY_SIZE = 30
 
# System-map bounds — objects placed within this area
SYS_W = 70
SYS_H = 50
SYS_MARGIN = 5

# --- Economy -----------------------------------------------------------------
 
def _generate_market(archetype_name, seq):
    """
    Generate a market dict for a planet or station based on archetype.
    Exported goods are cheap, imported goods are expensive,
    neutral goods are at base price. Military systems return None.
    """
    archetype = ARCHETYPES[archetype_name]
 
    if archetype.get("no_market"):
        return None
 
    market = {}
 
    for commodity in COMMODITIES:
        base = BASE_PRICES[commodity]
 
        if commodity in archetype["exports"]:
            # Produced here — sell cheap, with small random variation
            variation = (seq.next_seed() % 5) - 2   # -2 to +2
            market[commodity] = max(1, int(base * 0.6) + variation)
 
        elif commodity in archetype["imports"]:
            # Needed here — buy expensive
            variation = (seq.next_seed() % 7) - 3   # -3 to +3
            market[commodity] = int(base * 1.5) + variation
 
        else:
            # Neutral — base price with small variation
            variation = (seq.next_seed() % 5) - 2
            market[commodity] = max(1, base + variation)
 
    return market

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
    system.archetype = "Trade Hub"
    system.description = "Humanity's birthplace and the heart of interstellar trade."

    e_market = _generate_market("Trade Hub", SeedSequence(12345))
    m_market = _generate_market("Trade Hub", SeedSequence(67890))

    system.planets.append(
        Planet(
            20,
            20,
            "Earth",
            "United Nations",
            12345,
            (0, 0, 255),
            e_market,
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
            m_market,
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Earth Orbital",
            "United Nations",
            e_market,
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
    system.archetype = "Frontier"
    system.description = "A remote system on the edge of explored space."

    market = _generate_market("Frontier", SeedSequence(11111))

    system.planets.append(
        Planet(
            20,
            20,
            "New Horizon",
            "Independent",
            11111,
            (0, 0, 255),
            market
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Vega Prime",
            "Independent",
            market
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
    
    archetype_name = ARCHETYPE_NAMES[seq.next_seed() % len(ARCHETYPE_NAMES)]
    archetype = ARCHETYPES[archetype_name]

    system = StarSystem(name)
    system.archetype = archetype_name
    system.description = archetype["description"]
    used = _used_positions(system)
 
    # Planet and station counts come from archetype ranges
    p_min, p_max = archetype["planets"]
    s_min, s_max = archetype["stations"]
    num_planets  = p_min + seq.next_seed() % (p_max - p_min + 1)
    num_stations = s_min + seq.next_seed() % (s_max - s_min + 1)
 
    for _ in range(num_planets):
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
 
    for _ in range(num_stations):
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
    Wire jump points based on proximity.
    Each star connects to its 1-2 nearest neighbors, two-way.
    """
    star_map = {star.name: star for star in stars}

    # Sort all pairs by distance
    pairs = []
    for i, a in enumerate(stars):
        for j, b in enumerate(stars):
            if j <= i:
                continue
            dist = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
            pairs.append((dist, a.name, b.name))

    pairs.sort(key=lambda p: p[0])

    # Track how many connections each star has
    connection_count = {star.name: 0 for star in stars}
    max_connections = 3

    for dist, a_name, b_name in pairs:
        # Skip if both stars already have max connections
        if connection_count[a_name] >= max_connections and connection_count[b_name] >= max_connections:
            continue

        # Skip if already connected
        a_star = star_map[a_name]
        b_star = star_map[b_name]
        existing = {jp.destination for jp in a_star.system.jump_points}
        if b_name in existing:
            continue

        # Add A -> B
        used_a = _used_positions(a_star.system)
        x, y = _free_pos(master_seq, used_a)
        cost = 10 + master_seq.next_seed() % 41
        a_star.system.jump_points.append(
            JumpPoint(x, y, f"{a_name} -> {b_name}", a_name, b_name, cost)
        )

        # Add B -> A (return)
        used_b = _used_positions(b_star.system)
        rx, ry = _free_pos(master_seq, used_b)
        b_star.system.jump_points.append(
            JumpPoint(rx, ry, f"{b_name} -> {a_name}", b_name, a_name, cost)
        )

        connection_count[a_name] += 1
        connection_count[b_name] += 1

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