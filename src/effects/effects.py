"""Visual effects: star twinkle, spinning station glyphs, background rain."""

import math

# ---------------------------------------------------------------------------
# Twinkle (used for stars) and also in the title screen 
# ---------------------------------------------------------------------------

def twinkle_color(base_color, t, speed=2.0, phase=0.0):
    """Pulse a base RGB color's brightness over time using a sine wave."""
    brightness = (math.sin(t * speed + phase) + 1) / 2
    return tuple(int(c * (0.5 + 0.5 * brightness)) for c in base_color)


# ---------------------------------------------------------------------------
# Spin (used for stations)
# ---------------------------------------------------------------------------

SPIN_FRAMES = ["-", "\\", "|", "/"]


def get_spin_frame(t, speed=8.0, phase=0.0):
    """Return the current frame of a rotating - \\ | / animation."""
    index = int((t * speed + phase)) % len(SPIN_FRAMES)
    return SPIN_FRAMES[index]