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
    if not state.look_mode:
        return

    console.print(state.look_x, state.look_y, "X", fg=(255, 255, 0))

    if look_object is None:
        console.print(1, height - 2, "Looking at: empty space")

    elif hasattr(look_object, "govement"):  # Planet
        console.print(1, height - 4, f"Planet: {look_object.name}")
        console.print(1, height - 3, f"Government: {look_object.govement}")
        console.print(1, height - 2, f"Faction: {look_object.faction if hasattr(look_object, 'faction') else 'Unknown'}")

    elif hasattr(look_object, "faction"):  # Station
        console.print(1, height - 3, f"Station: {look_object.name}")
        console.print(1, height - 2, f"Faction: {look_object.faction}")

    elif hasattr(look_object, "destination"):  # JumpPoint
        console.print(1, height - 3, f"Jump Point -> {look_object.destination}")
        console.print(1, height - 2, f"Cost: {look_object.cost} credits")

    elif hasattr(look_object, "system"):  # Star (galaxy screen)
        console.print(1, height - 3, f"Star: {look_object.name}")
        console.print(1, height - 2, f"[{look_object.system.archetype}]")

    console.print(1, height - 5, "X - Stop looking")