"""Render the SYSTEM screen (planets, spinning stations, player marker)."""

import time

from core import state
from effects.effects import get_spin_frame


def draw(console, width, height, system):
    state.current_object = None

    console.print(
        width // 2 - len(system.name) // 2,
        1,
        system.name,
    )

    for planet in system.planets:
        console.print(planet.x, planet.y, "P", fg=planet.color)

        if state.system_player_x == planet.x and state.system_player_y == planet.y:
            state.current_object = planet

    t = time.time()

    for station in system.stations:
        frame = get_spin_frame(t, speed=8.0, phase=3)
        console.print(station.x, station.y, frame, fg=(255, 255, 255))

        if state.system_player_x == station.x and state.system_player_y == station.y:
            state.current_object = station

    for jumppoint in system.jump_points:
        console.print(jumppoint.x, jumppoint.y, "J", fg=(255, 255, 255))

        if state.system_player_x == jumppoint.x and state.system_player_y == jumppoint.y:
            state.current_object = jumppoint

    console.print(state.system_player_x, state.system_player_y, "@", fg=(255, 255, 255))

    if state.current_object:
        console.print(1, height - 2, f"Object: {state.current_object.name}")
        console.print(1, height - 3, "ENTER - Visit")