"""Render the VICTORY screen (classic UI)"""

from core import state


def draw(console, width, height):
    console.print(width // 2 - 9, height // 2 - 4, "LOAN PAID OFF!", fg=(0, 255, 0))
    console.print(width // 2 - 15, height // 2, "The ship is yours, pilot.")
    console.print(width // 2 - 14, height // 2 + 2, f"Days taken: {state.day}")
    console.print(width // 2 - 14, height // 2 + 4, "Press c to keep flying, q to quit")
