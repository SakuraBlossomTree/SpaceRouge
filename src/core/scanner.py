"""Long-Range System Scanner configuration and range helpers.

The scanner is a standard ship system (radius 1 jump), extended by the
shipyard upgrade ``scanrange``.  Every distance is measured through the
actual jump-gate network, never straight-line distance on the galaxy chart.

All scanner levels live here so adding another one only means appending a
radius and a shipyard offer.  ``RADII`` is indexed by upgrade level:
level 0 is the standard scanner, level 1 is the first purchased upgrade.
"""

from core import state

UPGRADE_ID = "scanrange"

# Upgrade level -> scanner radius in jump-gate hops.
RADII = (1, 2, 3, 4)

# Systems this many jumps beyond the scanner radius are still visible on the
# system map, but without planet/station/jump-gate labels.
OBSERVED_EXTRA = 1

# Names shown in the Exchange / shipyard for each level.
LEVEL_NAMES = ("Standard", "Improved", "Advanced", "Experimental")


def level():
    """Current scanner upgrade level (0 = the standard, free scanner)."""
    try:
        return max(0, min(len(RADII) - 1, int(state.upgrades.get(UPGRADE_ID, 0))))
    except (TypeError, ValueError, AttributeError):
        return 0


def radius(level_override=None):
    """Scanner radius in jump-gate hops for the current (or given) level."""
    if level_override is None:
        lv = level()
    else:
        try:
            lv = max(0, min(len(RADII) - 1, int(level_override)))
        except (TypeError, ValueError):
            lv = 0
    return RADII[lv]


def observed_radius(level_override=None):
    """Outer edge of the unlabelled map preview, in jump-gate hops."""
    return radius(level_override) + OBSERVED_EXTRA


def level_name(level_override=None):
    """Human-readable scanner generation, e.g. "Improved"."""
    lv = level() if level_override is None else level_override
    try:
        lv = max(0, min(len(LEVEL_NAMES) - 1, int(lv)))
    except (TypeError, ValueError):
        lv = 0
    return LEVEL_NAMES[lv]


def range_text(level_override=None):
    """'1 jump' / '3 jumps' for the scanner's current radius."""
    n = radius(level_override)
    return f"{n} jump{'s' if n != 1 else ''}"


def max_level():
    return len(RADII) - 1


def restore_level(saved_level):
    """Apply a saved scanner upgrade level, clamped to a valid range."""
    try:
        lv = max(0, min(max_level(), int(saved_level)))
    except (TypeError, ValueError):
        lv = 0
    state.upgrades[UPGRADE_ID] = lv
    return lv
