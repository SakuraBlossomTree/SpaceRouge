"""A small stand-in for python-tcod, so the desktop game code runs on pygame.

Only the parts SpaceRouge uses are implemented:
  tcod.console.Console   - character grid (ch / fg / bg arrays) + drawing
  tcod.event             - KeySym, KeyDown, MouseWheel, Quit, Modifier
  tcod.tileset           - load_tilesheet() returns a reference the renderer uses
  tcod.context           - constants only; the pygame app provides the context

The real drawing to the screen happens in mobile/presenter.py.
"""

from . import console, event, tileset, context, constants  # noqa: F401

__version__ = "spacerouge-shim"
