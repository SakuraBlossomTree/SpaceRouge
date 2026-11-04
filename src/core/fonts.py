"""Font presets + persisted settings.

Every font is a CP437 tilesheet PNG loaded with tcod.tileset.load_tilesheet.
The sans sheets are generated from DejaVu Sans Mono by tools/make_font.py.
F10 cycles the presets in-game, F9 switches between the modern and classic
UI; both choices are saved to settings.json.
"""

import json
from pathlib import Path

import tcod

# name, path, columns, rows
FONTS = [
    ("Sans", "assets/fonts/sans_10x14.png", 16, 16),
    ("Sans Large", "assets/fonts/sans_12x17.png", 16, 16),
    ("Sans Small", "assets/fonts/sans_8x12.png", 16, 16),
    ("Classic", "Haberdash_curses_12x12.png", 16, 16),
]

SETTINGS_PATH = Path("settings.json")

_settings = None


def settings():
    global _settings
    if _settings is None:
        try:
            _settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _settings = {}
    return _settings


def save_settings():
    try:
        SETTINGS_PATH.write_text(json.dumps(settings(), indent=2), encoding="utf-8")
    except OSError:
        pass


# --- UI mode ------------------------------------------------------------------
# "modern" = the redesigned framed UI, "classic" = the original screens.
# Each mode remembers its own font (classic defaults to the pixel font).

CLASSIC_FONT = 3


def ui_mode():
    from core import state
    if not state.UI_TOGGLE:
        return "modern"          # toggle switched off: always the modern UI
    return "classic" if settings().get("ui") == "classic" else "modern"


def _font_key():
    return "classic_font" if ui_mode() == "classic" else "font"


def current_index():
    default = CLASSIC_FONT if ui_mode() == "classic" else 0
    i = settings().get(_font_key(), default)
    return i if isinstance(i, int) and 0 <= i < len(FONTS) else default


def toggle_ui(context):
    """Switch modern <-> classic UI (and to that mode's font). Returns new mode."""
    settings()["ui"] = "modern" if ui_mode() == "classic" else "classic"
    save_settings()
    if context is not None:
        _, tileset = load()
        context.change_tileset(tileset)
    return ui_mode()


def current_name():
    return FONTS[current_index()][0]


def load(index=None):
    """Load a font preset; falls back to the classic sheet if a file is missing."""
    if index is None:
        index = current_index()
    for i in [index] + list(range(len(FONTS))):
        _, path, cols, rows = FONTS[i]
        if Path(path).exists():
            return i, tcod.tileset.load_tilesheet(path, cols, rows, tcod.tileset.CHARMAP_CP437)
    raise FileNotFoundError("No font tilesheets found")


def cycle(context):
    """Switch to the next font preset. Returns the new font's name."""
    index, tileset = load((current_index() + 1) % len(FONTS))
    if context is not None:
        context.change_tileset(tileset)
    settings()[_font_key()] = index
    save_settings()
    return FONTS[index][0]
