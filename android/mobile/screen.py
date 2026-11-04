"""Mobile frame composition: the game fills the whole console.

Unlike the PC layout (map viewport + 38-column sidebar), the mobile build
draws the map edge to edge; ship status, icons and buttons are drawn by
pygame on top (mobile/touch.py).

* Star systems are generated for an 80x60 map. They're drawn at that size
  and copied into the screen centred, scrolling up/down to follow the ship
  when the screen has fewer than 60 rows.
* The galaxy chart, combat and hyperspace draw at the full console size.
* Menus (station, market, ...) and overlays (cargo, log, ...) are drawn
  centred on the full screen over a dimmed map.
"""

import tcod
from core import state
from render import ui, title, story, galaxy, system as system_render, jumppoint
from render import hyperspace, location, market, inventory, messages
from render import missions, mission_log, gameover, planet, tutorial_panel, exchange
from render import help as handbook
from render import combat as combat_render

SYS_W, SYS_H = 80, 60
MODALS = ("JUMPPOINT", "LOCATION", "MARKET", "MISSIONS")
OVERLAYS = ("INVENTORY", "MESSAGES", "MISSION_LOG", "HELP", "EXCHANGE")
FULLSCREEN = ("TITLE", "STORY", "GAME_OVER")

_sys_con = tcod.console.Console(SYS_W, SYS_H)

# where the system map sits on screen (console cells) - used for tap-to-fly
view = {"ox": 0, "oy": 0}


def configure(cols, rows):
    """Tell the shared UI code how big the screen is."""
    ui.MAP_W, ui.MAP_H = cols, rows
    ui.SCREEN_W, ui.SCREEN_H = cols, rows
    ui.MAP_X = ui.MAP_Y = 0
    from core import galaxy_view
    galaxy_view.configure(cols, rows)
    galaxy.MINIMAP_INSET = int(cols * 0.22) + 1     # keep it left of the right-hand panel


def _system(console):
    W, H = console.width, console.height
    system = state.current_system
    if system is None:
        return
    # faint stars across the whole screen, then the 80x60 system map on top
    system_render.draw_background(console, system.name, W, H)
    _sys_con.clear(bg=ui.BG)
    system_render.draw(_sys_con, SYS_W, SYS_H, system)

    focus = state.look_y if state.look_mode else state.system_player_y
    cam = 0 if H >= SYS_H else max(0, min(SYS_H - H, focus - H // 2))
    ox = (W - SYS_W) // 2
    oy = (H - SYS_H) // 2 if H > SYS_H else 0
    src_x = max(0, -ox)
    w = min(SYS_W - src_x, W)
    h = min(SYS_H - cam, H)
    _sys_con.blit(console, max(0, ox), oy, src_x, cam, w, h)
    view["ox"], view["oy"] = ox, oy - cam


def _draw_view(con, gs, stars, depth=0):
    W, H = con.width, con.height
    if gs == "GALAXY":
        galaxy.draw(con, W, H, stars)
    elif gs == "SYSTEM":
        _system(con)
    elif gs == "HYPERSPACE":
        hyperspace.draw(con, W, H)
    elif gs == "COMBAT":
        combat_render.draw(con, W, H)
    elif gs == "PLANET":
        planet.draw(con)
    elif gs in MODALS:
        _system(con)
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
        }[gs]()


def compose(console, stars, title_text, story_text):
    gs = state.game_state
    W, H = console.width, console.height
    console.clear(bg=ui.BG)
    if gs == "TITLE":
        title.draw(console, W, H, title_text)
        return
    if gs == "STORY":
        story.draw(console, H, story_text, W)
        return
    if gs == "GAME_OVER":
        gameover.draw(console, W, H)
        return
    _draw_view(console, gs, stars)
    tutorial_panel.draw(console, corner="top-center")
