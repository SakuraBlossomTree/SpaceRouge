"""World generation: star systems, planet surfaces, station hubs."""

import random

from core.entities import Star, StarSystem, Planet, Station, JumpPoint

WIDTH = 80
HEIGHT = 60

STAR_NAMES = [
    "Sol",
    "Alpha Centauri",
    "Sirius",
    "Vega",
    "Altair",
    "Polaris",
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
            {"Food": 2},
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
            {"Food": 1},
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Earth Orbital",
            "United Nations",
            {"Food": 2},
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
            {"Food": 4}
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Vega Prime",
            "Independent",
            {"Food": 3}
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


def generate_stars():
    """Create the galaxy's stars, with Sol given its hand-built system."""
    stars = []

    for i in range(len(STAR_NAMES)):
        stars.append(
            Star(
                random.randint(0, WIDTH - 1),
                random.randint(0, HEIGHT - 1),
                STAR_NAMES[i],
                random.choice(list(STAR_TYPES.keys()))
            )
        )

    for star in stars:

        if star.name == "Sol":
            star.type = "Yellow Dwarf"
            star.system = create_sol_system()

        elif star.name == "Vega":
            star.system = create_vega_system()

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