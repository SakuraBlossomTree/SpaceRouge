"""Render the MARKET screen (buy/sell Food)."""

from core import state


def draw(console, width):
    food_count = sum(1 for item in state.inventory.items if item.name == "Food")

    console.print(
        width // 2 - len(state.current_location.name) // 2,
        2,
        f"{state.current_location.name} Market",
    )

    console.print(2, 4, f"Credits: {state.credits}")
    console.print(2, 6, f"You own: {food_count} Food")

    food_price = state.current_location.market["Food"]

    console.print(2, 8, f"[1] Buy Food ({food_price} credits)")
    console.print(2, 10, f"[2] Sell Food ({food_price} credits)")

    console.print(2, 12, "ESC - Leave")