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
from effects import transitions as anim
from render import ui, hud, launch
from render import title, story, galaxy, system as system_render, jumppoint
from render import hyperspace, location, market, inventory, messages
from render import missions, mission_log, gameover, victory, planet, tutorial_panel
from render import shipyard as shipyard_render
from render import help as handbook, exchange, radio
from render import notebook as notebook_render
from render import pricelog as pricelog_render
from render import combat as combat_render

MODALS = ("JUMPPOINT", "LOCATION", "MARKET", "MISSIONS", "SHIPYARD")
OVERLAYS = ("INVENTORY", "MESSAGES", "MISSION_LOG", "HELP", "EXCHANGE", "RADIO", "NOTEBOOK", "PRICELOG")
FULLSCREEN = ("TITLE", "STORY", "LAUNCH", "GAME_OVER", "VICTORY")

# How long a menu takes to unfold / a screen to fade in (seconds)
UNFOLD_TIME = 0.22
FADE_TIME = 0.25


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
        under = con.rgb.copy()
        {
            "JUMPPOINT": lambda: jumppoint.draw(con, W, H),
            "LOCATION": lambda: location.draw(con, W, H),
            "MARKET": lambda: market.draw(con, W, H),
            "MISSIONS": lambda: missions.draw(con, W, H),
            "SHIPYARD": lambda: shipyard_render.draw(con, W, H),
        }[gs]()
        if depth == 0:
            anim.unfold(con, under, anim.progress("screen", UNFOLD_TIME))
    elif gs in OVERLAYS:
        base = state.overlay_return or "SYSTEM"
        if depth < 3 and base not in OVERLAYS:
            _draw_view(con, base, stars, depth + 1)
        ui.dim_console(con, 0.28)
        under = con.rgb.copy()
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
        if depth == 0:
            anim.unfold(con, under, anim.progress("screen", UNFOLD_TIME))


def _quit_box(console):
    """'Quit the game?' confirmation, centred on the whole window."""
    w, h = 40, 7
    x, y = (console.width - w) // 2, (console.height - h) // 2
    console.draw_rect(x + 1, y + 1, w, h, ord(" "), bg=(0, 0, 0))
    if state.game_state == "TITLE":
        ui.frame(console, x, y, w, h, "Quit", fg=ui.BAD)
        ui.center(console, x + w // 2, y + 2, "Quit the game?", fg=ui.TEXT)
        ui.hint_row_centered(console, x + w // 2, y + 5, [("Y", "Quit"), ("N/ESC", "Cancel")])
        return
    ui.frame(console, x, y, w, h, "Main menu", fg=ui.BAD)
    ui.center(console, x + w // 2, y + 2, "Back to the main menu?", fg=ui.TEXT)
    ui.center(console, x + w // 2, y + 3, "Your galaxy progress is saved.", fg=ui.DIM)
    ui.hint_row_centered(console, x + w // 2, y + 5, [("Y", "Main menu"), ("N/ESC", "Keep playing")])


def compose(console, map_con, stars, title_text, story_text):
    gs = state.game_state
    anim.touch("screen", gs)
    anim.touch("quit", state.quit_confirm)
    anim.touch("quick", state.quick_menu)
    _compose(console, map_con, stars, title_text, story_text)
    if state.quit_confirm:
        ui.dim_console(console, 0.4)
        under = console.rgb.copy()
        _quit_box(console)
        anim.unfold(console, under, anim.progress("quit", UNFOLD_TIME))
    _screen_transition(console, gs)


def _screen_transition(console, gs):
    """Whole-screen fades: new screens fade up from black, and the launch
    sequence's white-out fades down into the first view of the game. Menus
    opening and closing over a screen have their own animation, so they are
    left alone."""
    if gs in MODALS or gs in OVERLAYS:
        return
    prev = anim.previous("screen")
    if prev == "LAUNCH":
        anim.flash_in(console, anim.progress("screen", 0.9))
    elif prev not in MODALS and prev not in OVERLAYS:
        anim.fade_in(console, 0.15 + 0.85 * anim.progress("screen", FADE_TIME))


def _compose(console, map_con, stars, title_text, story_text):
    gs = state.game_state
    console.clear(bg=ui.BG)

    if gs == "TITLE":
        title.draw(console, ui.SCREEN_W, ui.SCREEN_H, title_text)
        return
    if gs == "STORY":
        story.draw(console, ui.SCREEN_H, story_text, ui.SCREEN_W)
        return
    if gs == "LAUNCH":
        launch.draw(console, ui.SCREEN_W, ui.SCREEN_H)
        return
    if gs == "GAME_OVER":
        gameover.draw(console, ui.SCREEN_W, ui.SCREEN_H)
        return
    if gs == "VICTORY":
        victory.draw(console, ui.SCREEN_W, ui.SCREEN_H)
        return

    map_con.clear(bg=ui.BG)
    _draw_view(map_con, gs, stars)
    tutorial_panel.draw(map_con)
    if state.quick_menu:
        from render import quickmenu as quick_render
        under = map_con.rgb.copy()
        quick_render.draw(map_con)
        anim.unfold(map_con, under, anim.progress("quick", UNFOLD_TIME))

    t, rt = _viewport_title(gs)
    ui.frame(console, 0, 0, ui.MAP_W + 2, ui.MAP_H + 2, t, right_title=rt,
             bg=ui.BG, clear=False)
    map_con.blit(console, ui.MAP_X, ui.MAP_Y)

    hud.draw(console)
