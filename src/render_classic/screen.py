"""Classic UI: the original SpaceRouge screens on a single 80x60 console.

This is the pre-redesign interface, kept so you can switch back with F9.
Game logic and input are shared with the modern UI; only drawing differs.
The Pilot's Handbook (H) and the tutorial card reuse the modern widgets.
"""

from core import state
from render_classic import title, story, galaxy, system as system_render, jumppoint
from render_classic import hyperspace, hud, planet, location, market, inventory
from render_classic import messages, missions, mission_log, gameover
from render_classic import combat as combat_render
from render import help as handbook, tutorial_panel, exchange

WIDTH, HEIGHT = 80, 60


def compose(console, stars, title_text, story_text):
    console.clear()
    gs = state.game_state

    if gs == "TITLE":
        title.draw(console, WIDTH, HEIGHT, title_text)
    elif gs == "STORY":
        story.draw(console, HEIGHT, story_text)
    elif gs == "LAUNCH":
        from render import launch
        launch.draw(console, WIDTH, HEIGHT)
        return
    elif gs == "GALAXY":
        galaxy.draw(console, WIDTH, HEIGHT, stars)
    elif gs == "SYSTEM":
        system_render.draw(console, WIDTH, HEIGHT, state.current_system)
    elif gs == "JUMPPOINT":
        jumppoint.draw(console, WIDTH, HEIGHT)
    elif gs == "HYPERSPACE":
        hyperspace.draw(console, WIDTH, HEIGHT)
    elif gs == "PLANET":
        planet.draw(console)
    elif gs == "LOCATION":
        location.draw(console, WIDTH)
    elif gs == "MARKET":
        market.draw(console, WIDTH)
    elif gs == "INVENTORY":
        inventory.draw(console, WIDTH)
    elif gs == "MESSAGES":
        messages.draw(console, WIDTH, HEIGHT)
    elif gs == "MISSION_LOG":
        mission_log.draw(console, WIDTH)
    elif gs == "MISSIONS":
        missions.draw(console, WIDTH)
    elif gs == "COMBAT":
        combat_render.draw(console, WIDTH, HEIGHT)
    elif gs == "GAME_OVER":
        gameover.draw(console, WIDTH, HEIGHT)
    elif gs == "VICTORY":
        from render_classic import victory
        victory.draw(console, WIDTH, HEIGHT)
    elif gs == "HELP":
        handbook.draw(console, WIDTH, HEIGHT)
    elif gs == "EXCHANGE":
        exchange.draw(console, WIDTH, HEIGHT)

    hud.draw(console, WIDTH, HEIGHT)
    # Map screens use the bottom rows for text, menu screens use the top rows
    corner = "top-right" if gs in ("SYSTEM", "GALAXY") else "bottom-left"
    tutorial_panel.draw(console, corner=corner)
