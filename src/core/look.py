"""Shared look-mode rendering helper."""

from core import state

def check(obj, look_object):
    """Return obj if the look cursor is on it, otherwise return look_object unchanged."""
    if state.look_mode and state.look_x == obj.x and state.look_y == obj.y:
        return obj
    return look_object

def draw(console, height):
    """Draw the look cursor and description line."""
    if not state.look_mode:
        return
    console.print(state.look_x, state.look_y, "X", fg=(255, 255, 0))
    # filled in by caller via return value of check()

def draw_result(console, height, look_object):
    """Draw cursor glyph and description. Call after all objects are checked."""
    if not state.look_mode:
        return
    console.print(state.look_x, state.look_y, "X", fg=(255, 255, 0))
    if look_object:
        console.print(1, height - 2, f"Looking at: {look_object.name}")
    else:
        console.print(1, height - 2, "Looking at: empty space")
    console.print(1, height - 3, "X - Stop looking")