"""Render the MISSIONS screen."""

from core import state


def draw(console, width):
    console.print(width // 2 - 4, 2, "MISSIONS BOARD")

    y = 5
    for index, mission in enumerate(state.visible_missions):
        if index == state.selected_mission_index:
            prefix = "> "
        else:
            prefix = " "

        line = f"{prefix}{mission.title} ({mission.status})"
        console.print(4, y, line)
        y+=1

    selected = state.missions[state.selected_mission_index]
    console.print(4, y+2, selected.description)
    console.print(4, y+3, f"Reward: {selected.reward_credits} credits")

    console.print(width // 2 - 4, 20, "Press ESC to leave")