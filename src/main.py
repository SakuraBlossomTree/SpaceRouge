"""Space Rogue - entry point.

Sets up the tcod context/console, loads assets, and runs the main
loop: update -> draw -> present -> handle events.

All drawing is handled by render/screen.py (layout + every screen).
"""

import os
import sys
import time

# Built with PyInstaller (build_exe.bat): the game's files (story, fonts, music)
# and its saves live in the bundle folder, and every path in the game is
# relative, so start there.
if getattr(sys, "frozen", False):
    os.chdir(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))

import tcod

from pathlib import Path
from core import state, audio, fonts, tutorial, newgame
from core.events import handle_event, update_hyperspace
from core import travel
from render import story, ui
from render.screen import compose
from render_classic import screen as classic_screen

MUSIC_FOLDER = "sfx/music"
TITLE_TRACK = "sfx/music/MyVeryOwnDeadShip.ogg"


def update_music():
    """Title theme on the title screen, silence for the story, then a
    shuffled playlist of the other tracks for the rest of the game."""
    gs = state.game_state
    if gs == "TITLE":
        audio.ensure_music(TITLE_TRACK)
    elif gs == "STORY":
        if audio.current_music_path:
            audio.stop_music()
    else:
        audio.ensure_playlist(MUSIC_FOLDER, exclude=[TITLE_TRACK])
    audio.update()

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    # Whole window: 80x60 map viewport + frame + 38-column sidebar
    console = tcod.console.Console(ui.SCREEN_W, ui.SCREEN_H)
    # The map viewport uses the same 80x60 size the world is generated for
    map_console = tcod.console.Console(ui.MAP_W, ui.MAP_H)
    # The classic (original) UI draws everything on one 80x60 console
    classic_console = tcod.console.Console(classic_screen.WIDTH, classic_screen.HEIGHT)

    state.story_texts = [
        load_text("story1.txt"),
        load_text("story2.txt")
    ]
    title_text = load_text("title.txt")

    # Galaxy from --seed N (or a new random one); the economy is built too.
    # The title screen can also load the last seed (L) or type one (S).
    newgame.startup()

    # Font: a sans-serif tilesheet by default; F10 cycles presets (core/fonts.py)
    _, tileset = fonts.load()

    if state.DEBUG:
        for star in state.stars:
            if star.name == "Sol":
                state.current_star = star
                state.current_system = star.system
                state.current_planet = star.system.planets[0]
                state.current_location = star.system.planets[0]
                break
        state.game_state = state.DEBUG_SCREEN

    state.last_story_time = time.time()

    with tcod.context.new(
        columns=ui.SCREEN_W,
        rows=ui.SCREEN_H,
        title="Space Rogue",
        tileset=tileset,
        sdl_window_flags=tcod.context.SDL_WINDOW_RESIZABLE,
    ) as context:

        frame_time = 1 / 60
        while True:
            frame_start = time.perf_counter()
            story_text = state.story_texts[state.story_index] if state.story_index < len(state.story_texts) else ""

            # --- Per-state updates ------------------------------------------
            if state.game_state == "STORY":
                story.update(story_text)
            elif state.game_state == "HYPERSPACE":
                update_hyperspace()
            travel.update_autopilot()
            tutorial.update()
            update_music()

            # --- Draw ---------------------------------------------------------
            if fonts.ui_mode() == "classic":
                classic_screen.compose(classic_console, state.stars, title_text, story_text)
                context.present(classic_console, keep_aspect=True, integer_scaling=False)
            else:
                compose(console, map_console, state.stars, title_text, story_text)
                context.present(console, keep_aspect=True, integer_scaling=False)

            # --- Events ----------------------------------------------------
            for event in tcod.event.get():
                if isinstance(event, tcod.event.Quit):
                    audio.shutdown()
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
                    for star in state.stars:
                        if star.name == "Sol":
                            state.current_star = star
                            state.current_system = star.system
                            break

                handle_event(event, story_text, context)

            # Cap at ~60 FPS so the loop doesn't spin a CPU core at 100%
            spare = frame_time - (time.perf_counter() - frame_start)
            if spare > 0:
                time.sleep(spare)


if __name__ == "__main__":
    main()