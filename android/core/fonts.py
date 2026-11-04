"""Font presets + persisted settings (mobile build).

Fonts are CP437 tilesheets. "Sans" comes in several sizes; the renderer
picks the biggest one that fits the screen. F10 (or the Font button on the
title screen) switches between Sans and the Classic pixel font.
"""

import json
from pathlib import Path

import tcod

# name, family, path of the default sheet
FONTS = [
    ("Sans", "sans", "assets/fonts/sans_10x14.png"),
    ("Classic", "classic", "assets/fonts/classic_12x12.png"),
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


# The mobile build only has the modern UI.
def ui_mode():
    return "modern"


def toggle_ui(context):
    return "modern"


def current_index():
    i = settings().get("font", 0)
    return i if isinstance(i, int) and 0 <= i < len(FONTS) else 0


def current_name():
    return FONTS[current_index()][0]


def load(index=None):
    if index is None:
        index = current_index()
    name, family, path = FONTS[index]
    return index, tcod.tileset.load_tilesheet(path, 16, 16, family=family)


def cycle(context):
    index, tileset = load((current_index() + 1) % len(FONTS))
    if context is not None:
        context.change_tileset(tileset)
    settings()["font"] = index
    save_settings()
    return FONTS[index][0]
