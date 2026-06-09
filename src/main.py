import tcod
import random
import time

WIDTH = 80
HEIGHT = 50

console = tcod.console.Console(WIDTH, HEIGHT)

player_x = 40
player_y = 25

system_player_x = 40
system_player_y = 25

class Star:
    def __init__(self, x, y, name):
        self.x = x
        self.y = y
        self.name = name

        self.system = StarSystem(name)

class StarSystem:
    def __init__(self, name):
        self.name = name

        self.planets = []
        self.stations = []
        self.jump_points = []

class Planet:
    def __init__(self, x, y, name, govement, seed):
        self.x = x
        self.y = y
        self.name = name
        self.govement = govement
        self.seed = seed

class Station:
    def __init__(self, x, y, name, faction):
        self.x = x
        self.y = y
        self.name = name
        self.faction = faction

class JumpPoint:
    def __init__(self, x, y, source, destination):
        self.x = x
        self.y = y
        self.name = "Jump Station"
        self.source = source
        self.destination = destination



STAR_NAMES = [
    "Sol",
    "Alpha Centauri",
    "Sirius",
    "Vega",
    "Altair",
    "Polaris",
]

stars = []

def create_sol_system():

    system = StarSystem("Sol")

    system.planets.append(
        Planet(
            20,
            20,
            "Earth",
            "United Nations"
        )
    )

    system.planets.append(
        Planet(
            30,
            25,
            "Mars",
            "United Nations"
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Earth Orbital",
            "United Nations"
        )
    )

    return system

for i in range(len(STAR_NAMES)):
    stars.append(Star(random.randint(0,WIDTH-1), random.randint(0, HEIGHT-1), STAR_NAMES[i]))

for star in stars:
    if star.name == "Sol":
        star.system = create_sol_system()

game_state = "GALAXY"

current_system = None

messages = []

def add_message(text):
    messages.append(text)

    if len(messages) > 10:
        messages.pop(0)

with tcod.context.new(
    columns=WIDTH,
    rows=HEIGHT,
    title="Space Rogue",
    tileset=None,
) as context:

    while True:
        console.clear()

        if game_state == "GALAXY":
            flash = int(time.time() * 2) % 2

            current_star = None

            on_star = False

            for star in stars:

                console.print(star.x, star.y, "*")
                
                if player_x == star.x and player_y == star.y:
                    on_star = True
                    current_star = star

            if on_star:
                if flash:
                    console.print(player_x, player_y, "@")
                else:
                    console.print(player_x, player_y, "*")
            else:
                console.print(player_x,player_y, "@")

            if current_star:
                console.print(
                    1,
                    HEIGHT - 1,
                    f"System: {current_star.name}"
                )
        
        elif game_state == "SYSTEM":
            console.print(
                WIDTH // 2 - len(current_system.name) // 2,
                1,
                current_system.name
            )

            for planet in current_system.planets:

                console.print(
                    planet.x,
                    planet.y,
                    "P"
                )

            for station in current_system.stations:

                console.print(
                    station.x,
                    station.y,
                    "S"
                )

            console.print(
                system_player_x,
                system_player_y,
                "@"
            )

            console.print(
                1,
                HEIGHT - 1,
                "ESC - Return to Galaxy"
            )

        context.present(console)

        for event in tcod.event.get():
            if isinstance(event, tcod.event.Quit):
                raise SystemExit()

            if isinstance(event, tcod.event.KeyDown):

                if game_state == "GALAXY":

                    if event.sym == tcod.event.KeySym.UP:
                        player_y -= 1

                    elif event.sym == tcod.event.KeySym.DOWN:
                        player_y += 1

                    elif event.sym == tcod.event.KeySym.LEFT:
                        player_x -= 1

                    elif event.sym == tcod.event.KeySym.RIGHT:
                        player_x += 1

                    elif event.sym == tcod.event.KeySym.RETURN:
                        if current_star:
                            current_system = current_star.system

                            system_player_x = WIDTH // 2
                            system_player_y = HEIGHT // 2

                            game_state = "SYSTEM"

                elif game_state == "SYSTEM":

                    if event.sym == tcod.event.KeySym.UP:
                        system_player_y -= 1

                    elif event.sym == tcod.event.KeySym.DOWN:
                        system_player_y += 1

                    elif event.sym == tcod.event.KeySym.LEFT:
                        system_player_x -= 1

                    elif event.sym == tcod.event.KeySym.RIGHT:
                        system_player_x += 1

                    elif event.sym == tcod.event.KeySym.ESCAPE:
                        game_state = "GALAXY"