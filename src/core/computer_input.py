"""Keyboard glue between tcod events and the in-game computer.

game_state "COMPUTER" is a full-window screen. events.handle_event hands
every event to handle() while it is active. The computer is not part of the
save file; its state lives only in this module.

Dev entry point:  python src/main.py --hack
"""

import time

import tcod

from core import fonts, state
from hacking import missions
from hacking.computer import Computer

computer = None
return_state = "TITLE"
_text_on = False
_last = None
_serial = None            # story_relay.RUN_SERIAL the computer was built for
SETTING = "hack_realtime"      # saved in settings.json with the other options

_KEYS = {
    tcod.event.KeySym.RETURN: "ENTER", tcod.event.KeySym.KP_ENTER: "ENTER",
    tcod.event.KeySym.BACKSPACE: "BACKSPACE", tcod.event.KeySym.ESCAPE: "ESC",
    tcod.event.KeySym.UP: "UP", tcod.event.KeySym.DOWN: "DOWN",
    tcod.event.KeySym.LEFT: "LEFT", tcod.event.KeySym.RIGHT: "RIGHT",
    tcod.event.KeySym.PAGEUP: "PAGEUP", tcod.event.KeySym.PAGEDOWN: "PAGEDOWN",
    tcod.event.KeySym.TAB: "TAB",
}


def open_computer(mission_id=None, back_to=None):
    """Switch the game to the computer screen (new run unless one exists)."""
    global computer, return_state, _serial
    from core import story_relay
    want = mission_id or missions.DEFAULT
    # a new computer for a different mission, or after the galaxy was rebuilt
    first = (computer is None or computer.mission_id != want
             or _serial != story_relay.RUN_SERIAL)
    if first:
        kw = {"realtime": bool(fonts.settings().get(SETTING, True))}
        computer = Computer(want, **kw)
        computer.on_realtime_change = _save_realtime
        _serial = story_relay.RUN_SERIAL
    computer.begin_boot(full=first)
    global _last
    _last = None
    return_state = back_to or state.game_state
    state.game_state = "COMPUTER"


def _save_realtime(value):
    fonts.settings()[SETTING] = bool(value)
    fonts.save_settings()


def update():
    """Per-frame clock for the real-time trace (called from main.py)."""
    global _last
    now = time.monotonic()
    dt = 0.0 if _last is None else min(1.0, now - _last)
    _last = now
    if computer is not None:
        computer.update(dt)
        from core import story_relay
        story_relay.on_computer_update(computer)
        from core import hackjobs
        hackjobs.on_computer_update(computer)


def _text_input(context, on):
    """tcod >= 19 sends no TextInput events until the window asks for them."""
    window = getattr(context, "sdl_window", None)
    if window is None:
        return
    try:
        (window.start_text_input if on else window.stop_text_input)()
    except Exception:
        pass


def close_computer(context=None):
    _text_input(context, False)
    state.game_state = return_state


def handle(event, context=None):
    """Called by events.handle_event for every event while on COMPUTER."""
    global _text_on
    if not _text_on:
        _text_input(context, True)
        _text_on = context is not None
    if isinstance(event, tcod.event.TextInput):
        computer.on_text(event.text)
    elif isinstance(event, tcod.event.KeyDown):
        key = _KEYS.get(event.sym)
        if key and computer.on_key(key) == "exit":
            _text_on = False
            close_computer(context)
