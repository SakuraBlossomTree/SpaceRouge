import tcod
import random
import time

WIDTH = 80
HEIGHT = 50

console = tcod.console.Console(WIDTH, HEIGHT)

player_x = 40
player_y = 25

class Star:
    def __init__(self, x, y):
        self.x = x
        self.y = y

stars = []

for _ in range(100):
    stars.append(Star(random.randint(0,WIDTH-1), random.randint(0, HEIGHT-1)))

with tcod.context.new(
    columns=WIDTH,
    rows=HEIGHT,
    title="Space Rogue",
    tileset=None,
) as context:

    while True:
        console.clear()

        flash = int(time.time() * 2) % 2

        on_star = False

        for star in stars:
            console.print(star.x, star.y, "*")
            
            if player_x == star.x and player_y == star.y:
                on_star = True

        if on_star:
            if flash:
                console.print(player_x, player_y, "@")
            else:
                console.print(player_x, player_y, "*")
        else:
            console.print(player_x,player_y, "@")

        context.present(console)

        for event in tcod.event.get():
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