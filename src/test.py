import random

STAR_TYPES = {
    "Red Dwarf": {
        "color": (255, 100, 100)
    },

    "Blue Dwarf": {
        "color": (100, 100, 255)
    },

    "White Dwarf": {
        "color": (255, 255, 255)
    }
}

star_type = random.choice(list(STAR_TYPES.keys()))

star_color = STAR_TYPES[star_type]["color"]

print(star_type, star_color)