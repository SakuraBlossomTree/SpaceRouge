"""Input events in tcod's shape (the game's input code is unchanged)."""

import enum

_NAMES = (
    "RETURN ESCAPE SPACE TAB BACKSPACE UP DOWN LEFT RIGHT PAGEUP PAGEDOWN HOME END "
    "PLUS EQUALS MINUS KP_PLUS KP_MINUS KP_ENTER".split()
    + [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + [f"N{i}" for i in range(10)]
    + [f"KP_{i}" for i in range(10)]
    + [f"F{i}" for i in range(1, 13)]
)
KeySym = enum.IntEnum("KeySym", _NAMES)


class Modifier(enum.IntFlag):
    NONE = 0
    SHIFT = 1
    CTRL = 2
    ALT = 4


class KeyDown:
    def __init__(self, sym, mod=Modifier.NONE, repeat=False):
        self.sym = sym
        self.mod = mod
        self.repeat = repeat

    def __repr__(self):
        return f"KeyDown({self.sym.name})"


class MouseWheel:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y


class Quit:
    pass


_queue = []


def post(ev):
    """The pygame app pushes translated events here."""
    _queue.append(ev)


def pending():
    """True if input is waiting (the app redraws immediately when it is)."""
    return bool(_queue)


def get():
    """Drain queued events (same use as tcod.event.get())."""
    out = list(_queue)
    _queue.clear()
    return out
