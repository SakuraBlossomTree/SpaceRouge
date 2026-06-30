"""Render the INVENTORY screen."""

from core import state
from collections import Counter


def draw(console, width):
    console.print(width // 2 - 4, 2, "INVENTORY")
    console.print(2, 4, f"Cargo: {state.inventory.used_space()}/{state.inventory.space}")

    counts = Counter(item.name for item in state.inventory.items)

    for i, (name, amount) in enumerate(counts.items()):
        console.print(2, 6 + i, f"{name} x{amount}")