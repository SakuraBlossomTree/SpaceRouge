"""Render the JUMPPOINT screen (jumppoint menu)."""

from core import state
from core.world import STAR_TYPES


def draw(console, width, height):

    title = state.current_object.name
    destination = state.current_object.destination

    destination_star = None

    for star in state.stars:
        if star.name == destination:
            destination_star = star
            break

    destination_color = (255, 255, 255)

    if destination_star:
        destination_color = STAR_TYPES[
            destination_star.type
        ]["color"]

    cost_color = (0, 255, 0)

    if state.current_object.cost > state.credits:
        cost_color = (255, 0, 0)

    title_x = width // 2 - len(title) // 2

    line1 = f"Travel to {destination}"
    line1_x = width // 2 - len(line1) // 2

    cost_text = f"Cost: {state.current_object.cost}"
    cost_x = width // 2 - len(cost_text) // 2

    line2 = "ENTER - Jump"
    line2_x = width // 2 - len(line2) // 2

    line3 = "ESC - Leave"
    line3_x = width // 2 - len(line3) // 2

    console.print(
        title_x,
        height // 2 - 4,
        title,
        fg=(0, 255, 255)
    )

    console.print(
        width // 2 - 20,
        height // 2 - 2,
        "========================================"
    )

    console.print(
        line1_x,
        height // 2,
        line1,
        fg=destination_color
    )

    console.print(
        cost_x,
        height // 2 + 3,
        cost_text,
        fg=cost_color
    )

    console.print(
        line2_x,
        height // 2 + 6,
        line2,
        fg=(0, 255, 0)
    )

    console.print(
        line3_x,
        height // 2 + 9,
        line3,
        fg=(255, 255, 255)
    )