"""Render the MESSAGES screen (message menu)."""

from core import state

def draw(console, width, height):

    console.print(
        width // 2 - 4,
        2,
        "Messages"
    )

    y = 5

    if len(state.messages) == 0:
        console.print(2, 10, "No messages here right now")

    for message in state.messages:
        console.print(2, y, message)
        y += 1