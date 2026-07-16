"""Render the GAME OVER screen"""

from core import state


def draw(console, width, height):

    console.print(
        width // 2 - len(str("GAME OVER")) // 2,
        height // 2 - 4,
        "GAME OVER",
        fg=(255, 0 , 0),
    )

    console.print(
        width // 2 - len(state.game_over_reason) // 2,
        height // 2,
        state.game_over_reason,
    )
    console.print(width // 2 - 8, height // 2 + 4, "Press q to quit")