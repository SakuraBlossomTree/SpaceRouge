import random

LIMIT = 2 ** 32

class SeedSequence:
    def __init__(self, seed=None):
        if seed is None:
            seed = random.randint(0, LIMIT - 1)

        self.seed = seed  # keep the original seed around for reference/debugging
        self.s0 = seed % LIMIT
        self.s1 = (seed * 2654435761 + 1) % LIMIT
        self.s2 = (seed * 2246822519 + 1) % LIMIT

    def step(self):
        new_value = (self.s0 + self.s1 + self.s2) % LIMIT
        self.s0, self.s1, self.s2 = self.s1, self.s2, new_value
        return self.s2

    def next_seed(self):
        return self.step()

def get_bits(value, start, width):
    mask = (1 << width) - 1
    return (value >> start) & mask

FIELD_MAP = {
    "x_position": ("s0", 0, 10),
    "y_position": ("s1", 0, 10),
    "food_price_raw": ("s2", 0, 10),
}

def read_field(sequence, field_name):
    source, start, width = FIELD_MAP[field_name]
    value = getattr(sequence, source)
    return get_bits(value, start, width)

def generate_food_price(seed=None):
    sequence = seed if isinstance(seed, SeedSequence) else SeedSequence(seed)
    raw = read_field(sequence, "food_price_raw")
    return raw % 20 + 5

def random_food_price():
    return generate_food_price(SeedSequence())