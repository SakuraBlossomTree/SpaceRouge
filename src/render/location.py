"""Render the LOCATION screen (station/planet hub menu)."""

from core import state


def draw(console, width):
    console.print(
        width // 2 - len(state.current_location.name) // 2,
        5,
        state.current_location.name,
    )

    console.print(10, 10, "[1] Trading Post")
    console.print(10, 11, "[2] Shipyard")
    console.print(10, 12, "[3] Missions Board")
    console.print(10, 13, "[4] Bar")

    console.print(10, 15, "ESC - Leave")