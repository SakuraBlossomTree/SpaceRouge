"""Render the MISSIONS LOG screen."""

from core import state

def draw(console, width):
    console.print(width // 2 - 5, 2, "ACTIVE MISSIONS")

    active = [m for m in state.missions if m.status == "active"]

    if not active:
        console.print(4, 5, "No active missions.")
        console.print(width // 2 - 4, 20, "Press ESC to leave")
        return

    y = 5
    for mission in active:
        console.print(4, y, f"{mission.title} -> {mission.destination}")
        y += 1

    console.print(width // 2 - 4, 20, "Press ESC to leave")