"""Render the MARKET screen (classic UI)."""

from collections import Counter

from core import state
from render.market import market_goods


def draw(console, width):
    if state.current_location is None:
        console.print(2, 2, "No location set (debug skip?)")
        return

    bar = "=" * 44
    bar_x = width // 2 - len(bar) // 2

    console.print(bar_x, 0, bar)

    title_text = f"{state.current_location.name} Market"

    console.print(
        width // 2 - len(title_text) // 2,
        2,
        title_text,
    )

    console.print(bar_x, 4, bar)

    console.print(2, 6, f"Credits: {state.credits}")
    console.print(2, 7, f"Cargo: {state.inventory.used_space()}/{state.inventory.space}")

    held = Counter(item.name for item in state.inventory.items if not item.mission_key)
    goods = market_goods()
    state.market_index = min(state.market_index, max(0, len(goods) - 1))

    for i, name in enumerate(goods):
        prefix = "> " if i == state.market_index else "  "
        price = state.current_location.market[name]
        console.print(2, 9 + i, f"{prefix}{name:<14} {price:>4} credits   you own: {held.get(name, 0)}")

    y = 10 + len(goods)
    console.print(2, y + 1, "UP/DOWN - Select   B - Buy   S - Sell")
    console.print(2, y + 3, "ESC - Leave")
