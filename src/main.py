import tcod

WIDTH = 80
HEIGHT = 50

console = tcod.console.Console(WIDTH, HEIGHT)

player_x = 40
player_y = 25

with tcod.context.new_terminal(
    columns=WIDTH,
    rows=HEIGHT,
    title="Space Rogue",
    tileset=None,
) as context:

    while True:
        console.clear()

        console.print(player_x, player_y, "@")

        context.present(console)

        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                raise SystemExit()

            if isinstance(event, tcod.event.KeyDown):

                if event.sym == tcod.event.KeySym.UP:
                    player_y -= 1

                elif event.sym == tcod.event.KeySym.DOWN:
                    player_y += 1

                elif event.sym == tcod.event.KeySym.LEFT:
                    player_x -= 1

                elif event.sym == tcod.event.KeySym.RIGHT:
                    player_x += 1