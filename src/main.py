"""Space Rogue - entry point.

Sets up the tcod context/console, loads assets, and runs the main
loop: update -> draw -> present -> handle events.
"""

import time

import tcod

from core import state
from core.events import handle_event
from core.world import generate_stars, WIDTH, HEIGHT
from render import title, story, galaxy, system as system_render
from render import planet, location, market, inventory


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    console = tcod.console.Console(WIDTH, HEIGHT)

    story_text = load_text("story.txt")
    title_text = load_text("title.txt")

    stars = generate_stars()

    tileset = tcod.tileset.load_tilesheet(
        "Haberdash_curses_12x12.png", 16, 16, tcod.tileset.CHARMAP_CP437
    )

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

            # --- Per-state update + draw ---------------------------------

            if state.game_state == "TITLE":
                title.draw(console, WIDTH, HEIGHT, title_text)

            elif state.game_state == "STORY":
                story.update(story_text)
                story.draw(console, HEIGHT, story_text)

            elif state.game_state == "GALAXY":
                galaxy.draw(console, WIDTH, HEIGHT, stars)

            elif state.game_state == "SYSTEM":
                system_render.draw(console, WIDTH, HEIGHT, state.current_system)

            elif state.game_state == "PLANET":
                planet.draw(console)

            elif state.game_state == "LOCATION":
                location.draw(console, WIDTH)

            elif state.game_state == "MARKET":
                market.draw(console, WIDTH)

            elif state.game_state == "INVENTORY":
                inventory.draw(console, WIDTH)

            context.present(console)

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
                ):
                    state.current_star = stars[0]
                    state.current_system = stars[0].system

                handle_event(event, story_text)


if __name__ == "__main__":
    main()