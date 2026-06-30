"""Render the PLANET screen (hub map walk-around)."""

from core import state


def draw(console):
    hub = state.current_planet.hub_map

    for y in range(len(hub)):
        for x in range(len(hub[y])):
            console.print(x, y, hub[y][x])

    console.print(state.planet_player_x, state.planet_player_y, "@")