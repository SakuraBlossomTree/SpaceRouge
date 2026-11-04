import random

LIMIT = 2 ** 32
_MASK = LIMIT - 1
_GOLDEN = 0x9E3779B9


def _mix32(z):
    """murmur3 finaliser: spreads every input bit across all output bits."""
    z &= _MASK
    z = ((z ^ (z >> 16)) * 0x85EBCA6B) & _MASK
    z = ((z ^ (z >> 13)) * 0xC2B2AE35) & _MASK
    return z ^ (z >> 16)


class SeedSequence:
    """Deterministic random numbers from a seed.

    Same seed -> same sequence, on every machine and every run. Each step
    advances a Weyl counter and scrambles it with a murmur3 finaliser, so
    every bit is well mixed (the old version's low bits repeated every few
    steps, which skewed anything picked with a small %).
    """

    def __init__(self, seed=None):
        if seed is None:
            seed = random.randint(0, LIMIT - 1)

        self.seed = int(seed) % LIMIT  # the original seed, for saving / debugging
        self._counter = _mix32(self.seed ^ 0x5BD1E995)
        # s0..s2 keep the last three outputs (used by read_field below)
        self.s0 = _mix32(self.seed)
        self.s1 = _mix32(self.seed + 1)
        self.s2 = _mix32(self.seed + 2)

    def step(self):
        self._counter = (self._counter + _GOLDEN) & _MASK
        value = _mix32(self._counter)
        self.s0, self.s1, self.s2 = self.s1, self.s2, value
        return value

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