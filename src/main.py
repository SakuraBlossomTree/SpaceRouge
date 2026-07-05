"""Space Rogue - entry point.

Sets up the tcod context/console, loads assets, and runs the main
loop: update -> draw -> present -> handle events.
"""

import time
import tcod
import random

from pathlib import Path
from core import state, audio
from core.events import handle_event, update_hyperspace
from core.world import generate_stars, WIDTH, HEIGHT
from core.save import save
from render import title, story, galaxy, system as system_render, jumppoint, hyperspace, hud
from render import planet, location, market, inventory, messages, missions, mission_log, gameover

MUSIC_PATH = Path("sfx/music")

music_tracks = list(MUSIC_PATH.glob("*.ogg"))

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    console = tcod.console.Console(WIDTH, HEIGHT)

    state.story_texts = [
        load_text("story1.txt"),
        load_text("story2.txt")
    ]
    title_text = load_text("title.txt")

    # track = random.choice(music_tracks)

    audio.play("sfx/music/MyVeryOwnDeadShip.ogg")

    state.stars, galaxy_seed = generate_stars()
    stars = state.stars
    state.galaxy_seed = galaxy_seed
    save(galaxy_seed)

    tileset = tcod.tileset.load_tilesheet(
        "Haberdash_curses_12x12.png", 16, 16, tcod.tileset.CHARMAP_CP437
    )

    if state.DEBUG:
        for star in stars:
            if star.name == "Sol":
                state.current_star = star
                state.current_system = star.system
                state.current_planet = star.system.planets[0]
                state.current_location = star.system.planets[0]
                break
        state.game_state = state.DEBUG_SCREEN

    state.last_story_time = time.time()
    last_frame_time = time.time()

    with tcod.context.new(
        columns=WIDTH,
        rows=HEIGHT,
        title="Space Rogue",
        tileset=tileset,
        sdl_window_flags=tcod.context.SDL_WINDOW_RESIZABLE,
    ) as context:

        while True:
            console.clear()

            story_text = state.story_texts[state.story_index] if state.story_index < len(state.story_texts) else ""

            # --- Per-state update + draw ---------------------------------

            if state.game_state == "TITLE":
                title.draw(console, WIDTH, HEIGHT, title_text)

            elif state.game_state == "STORY":
                story.update(story_text)
                audio.device.stop()
                story.draw(console, HEIGHT, story_text)

            elif state.game_state == "GALAXY":
                galaxy.draw(console, WIDTH, HEIGHT, stars)

            elif state.game_state == "SYSTEM":
                system_render.draw(console, WIDTH, HEIGHT, state.current_system)

            elif state.game_state == "JUMPPOINT":
                jumppoint.draw(console, WIDTH, HEIGHT)

            elif state.game_state == "HYPERSPACE":
                update_hyperspace()
                hyperspace.draw(console, WIDTH, HEIGHT)

            elif state.game_state == "PLANET":
                planet.draw(console)

            elif state.game_state == "LOCATION":
                location.draw(console, WIDTH)

            elif state.game_state == "MARKET":
                market.draw(console, WIDTH)

            elif state.game_state == "INVENTORY":
                inventory.draw(console, WIDTH)
            
            elif state.game_state == "MESSAGES":
                messages.draw(console, WIDTH, HEIGHT)

            elif state.game_state == "MISSION_LOG":
                mission_log.draw(console, WIDTH)

            elif state.game_state == "MISSIONS":
                missions.draw(console, WIDTH)

            elif state.game_state == "GAME_OVER":
                gameover.draw(console, WIDTH, HEIGHT)

            hud.draw(console, WIDTH, HEIGHT)

            context.present(console, keep_aspect=True)

            # --- Events ----------------------------------------------------

            for event in tcod.event.get():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()

                # Special case: leaving STORY for the first time needs to
                # pick the starting system, which main.py owns (stars list).
                if (
                    state.game_state == "STORY"
                    and isinstance(event, tcod.event.KeyDown)
                    and event.sym == tcod.event.KeySym.RETURN
                    and state.story_char_index >= len(story_text)
                    and state.current_star is None
                    and state.story_index >= len(state.story_texts) - 1  # only on last story
                ):
                    for star in stars:
                        if star.name == "Sol":
                            state.current_star = star
                            state.current_system = star.system
                            break

                handle_event(event, story_text, context)


if __name__ == "__main__":
    main()