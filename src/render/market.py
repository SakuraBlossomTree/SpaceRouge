"""Render the MARKET screen (buy/sell Food)."""

from core import state


def draw(console, width):
    if state.current_location is None:
        console.print(2, 2, "No location set (debug skip?)")
        return

    food_count = sum(1 for item in state.inventory.items if item.name == "Food")

    bar = "=" * 44
    bar_x = width // 2 - len(bar) // 2 

    console.print(bar_x,0, bar)

    title_text = f"{state.current_location.name} Market"

    console.print(
        width // 2 - len(title_text) // 2,
        2,
        title_text,
    )

    console.print(bar_x,4, bar)

    console.print(2, 4, f"Credits: {state.credits}")
    console.print(2, 6, f"You own: {food_count} Food")

    food_price = state.current_location.market["Food"]

    console.print(2, 8, f"[1] Buy Food ({food_price} credits)")
    console.print(2, 10, f"[2] Sell Food ({food_price} credits)")

    console.print(2, 12, "ESC - Leave")