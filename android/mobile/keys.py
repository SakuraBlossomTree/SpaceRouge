"""Translate pygame keyboard events into the game's tcod-style KeyDown."""

import pygame

import tcod

K = tcod.event.KeySym


def _build():
    table = {}

    def add(name, sym):
        code = getattr(pygame, name, None)
        if code is not None:
            table[code] = sym

    for name, sym in {
        "K_RETURN": K.RETURN, "K_KP_ENTER": K.RETURN, "K_ESCAPE": K.ESCAPE,
        "K_AC_BACK": K.ESCAPE,              # Android back button
        "K_SPACE": K.SPACE, "K_TAB": K.TAB, "K_BACKSPACE": K.BACKSPACE,
        "K_UP": K.UP, "K_DOWN": K.DOWN, "K_LEFT": K.LEFT, "K_RIGHT": K.RIGHT,
        "K_PAGEUP": K.PAGEUP, "K_PAGEDOWN": K.PAGEDOWN, "K_HOME": K.HOME, "K_END": K.END,
        "K_PLUS": K.PLUS, "K_EQUALS": K.EQUALS, "K_MINUS": K.MINUS,
        "K_KP_PLUS": K.KP_PLUS, "K_KP_MINUS": K.KP_MINUS,
    }.items():
        add(name, sym)
    for c in range(ord("a"), ord("z") + 1):
        add(f"K_{chr(c)}", K[chr(c).upper()])
    for d in range(10):
        add(f"K_{d}", K[f"N{d}"])
        add(f"K_KP{d}", K[f"KP_{d}"])
        add(f"K_KP_{d}", K[f"KP_{d}"])
    for f in range(1, 13):
        add(f"K_F{f}", K[f"F{f}"])
    return table


KEYMAP = _build()


def translate(event):
    """pygame KEYDOWN -> tcod.event.KeyDown, or None."""
    sym = KEYMAP.get(event.key)
    if sym is None:
        return None
    mod = tcod.event.Modifier.NONE
    if event.mod & pygame.KMOD_SHIFT:
        mod |= tcod.event.Modifier.SHIFT
    return tcod.event.KeyDown(sym, mod)
