"""Frame composition: decides what goes in the map viewport and the sidebar.

main.py calls compose() once per frame. Everything visual flows from here:

* full-screen states (TITLE / STORY / GAME_OVER) draw on the whole window
* everything else draws into the 80x60 map viewport, which is framed and
  blitted at (1, 1), and the sidebar is drawn to its right
* menu windows (station, market, missions, jump gate) are drawn over a
  dimmed system map; overlays (cargo, log, contracts) over a dimmed copy of
  whatever screen they were opened from
"""

from core import state
from render import ui, hud
from render import title, story, galaxy, system as system_render, jumppoint
from render import hyperspace, location, market, inventory, messages
from render import missions, mission_log, gameover, planet, tutorial_panel
from render import help as handbook, exchange, radio
from render import notebook as notebook_render
from render import pricelog as pricelog_render
from render import combat as combat_render

MODALS = ("JUMPPOINT", "LOCATION", "MARKET", "MISSIONS")
OVERLAYS = ("INVENTORY", "MESSAGES", "MISSION_LOG", "HELP", "EXCHANGE", "RADIO", "NOTEBOOK", "PRICELOG")
FULLSCREEN = ("TITLE", "STORY", "GAME_OVER")


def _viewport_title(gs):
    if gs in OVERLAYS:
        gs = state.overlay_return or "SYSTEM"
    if gs == "GALAXY":
        from core import galaxy_view
        return "Galaxy chart", f"zoom {galaxy_view.zoom_name()} · {len(state.stars)} systems"
    if gs == "COMBAT":
        return "Combat", "red alert"
    if gs == "HYPERSPACE":
        return "Hyperspace", ""
    if state.current_system is not None:
        return f"{state.current_system.name} system", state.current_system.archetype
    return "", ""


def _draw_view(con, gs, stars, depth=0):
    """Draw one game state into the map viewport console."""
    W, H = ui.MAP_W, ui.MAP_H

    if gs == "GALAXY":
        galaxy.draw(con, W, H, stars)
    elif gs == "SYSTEM":
        if state.current_system is not None:
            system_render.draw(con, W, H, state.current_system)
    elif gs == "HYPERSPACE":
        hyperspace.draw(con, W, H)
    elif gs == "COMBAT":
        combat_render.draw(con, W, H)
    elif gs == "PLANET":
        planet.draw(con)
    elif gs in MODALS:
        _draw_view(con, "SYSTEM", stars, depth + 1)
        ui.dim_console(con, 0.28)
        {
            "JUMPPOINT": lambda: jumppoint.draw(con, W, H),
            "LOCATION": lambda: location.draw(con, W, H),
            "MARKET": lambda: market.draw(con, W, H),
            "MISSIONS": lambda: missions.draw(con, W, H),
        }[gs]()
    elif gs in OVERLAYS:
        base = state.overlay_return or "SYSTEM"
        if depth < 3 and base not in OVERLAYS:
            _draw_view(con, base, stars, depth + 1)
        ui.dim_console(con, 0.28)
        {
            "INVENTORY": lambda: inventory.draw(con, W, H),
            "MESSAGES": lambda: messages.draw(con, W, H),
            "MISSION_LOG": lambda: mission_log.draw(con, W, H),
            "HELP": lambda: handbook.draw(con, W, H),
            "EXCHANGE": lambda: exchange.draw(con, W, H),
            "RADIO": lambda: radio.draw(con, W, H),
            "NOTEBOOK": lambda: notebook_render.draw(con, W, H),
            "PRICELOG": lambda: pricelog_render.draw(con, W, H),
        }[gs]()


def _quit_box(console):
    """'Quit the game?' confirmation, centred on the whole window."""
    w, h = 40, 7
    x, y = (console.width - w) // 2, (console.height - h) // 2
    console.draw_rect(x + 1, y + 1, w, h, ord(" "), bg=(0, 0, 0))
    ui.frame(console, x, y, w, h, "Quit", fg=ui.BAD)
    ui.center(console, x + w // 2, y + 2, "Quit the game?", fg=ui.TEXT)
    ui.center(console, x + w // 2, y + 3, "Unsaved progress will be lost.", fg=ui.DIM)
    ui.hint_row_centered(console, x + w // 2, y + 5, [("Y", "Quit"), ("N/ESC", "Keep playing")])


def compose(console, map_con, stars, title_text, story_text):
    _compose(console, map_con, stars, title_text, story_text)
    if state.quit_confirm:
        ui.dim_console(console, 0.4)
        _quit_box(console)


def _compose(console, map_con, stars, title_text, story_text):
    gs = state.game_state
    console.clear(bg=ui.BG)

    if gs == "TITLE":
        title.draw(console, ui.SCREEN_W, ui.SCREEN_H, title_text)
        return
    if gs == "STORY":
        story.draw(console, ui.SCREEN_H, story_text, ui.SCREEN_W)
        return
    if gs == "GAME_OVER":
        gameover.draw(console, ui.SCREEN_W, ui.SCREEN_H)
        return

    map_con.clear(bg=ui.BG)
    _draw_view(map_con, gs, stars)
    tutorial_panel.draw(map_con)
    if state.quick_menu:
        from render import quickmenu as quick_render
        quick_render.draw(map_con)

    t, rt = _viewport_title(gs)
    ui.frame(console, 0, 0, ui.MAP_W + 2, ui.MAP_H + 2, t, right_title=rt,
             bg=ui.BG, clear=False)
    map_con.blit(console, ui.MAP_X, ui.MAP_Y)

    hud.draw(console)
