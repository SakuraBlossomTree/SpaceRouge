"""Render the INVENTORY screen."""

from core import state


def draw(console, width):
    console.print(width // 2 - 4, 2, "INVENTORY")
    console.print(2, 4, f"Cargo: {state.inventory.used_space()}/{state.inventory.space}")

    for i, item in enumerate(state.inventory.items):
        console.print(2, 6 + i, item.name)