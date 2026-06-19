import tcod
import random
import time
import textwrap

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
    def __init__(self, x, y, name, govement, seed, market=None):
        self.x = x
        self.y = y
        self.name = name
        self.govement = govement
        self.seed = seed

        self.hub_map = None

        self.market = market or {}

class Station:
    def __init__(self, x, y, name, faction, market=None):
        self.x = x
        self.y = y
        self.name = name
        self.faction = faction

        self.hub_map = None

        self.market = market or {}

class JumpPoint:
    def __init__(self, x, y, source, destination):
        self.x = x
        self.y = y
        self.name = "Jump Station"
        self.source = source
        self.destination = destination

class Inventory:
    def __init__(self, space):
        self.space = space
        self.items = []

    def used_space(self):
        return sum(item.size for item in self.items)
    
    def free_space(self):
        return self.space - self.used_space()

class Item:
    def __init__(self, name, size):
        self.name = name
        self.size = size

credits = 100
inventory = Inventory(20)

FOOD = Item("Food", 2)



STAR_NAMES = [
    "Sol",
    # "Alpha Centauri",
    # "Sirius",
    # "Vega",
    # "Altair",
    # "Polaris",
]

stars = []

def create_sol_system():

    system = StarSystem("Sol")

    system.planets.append(
        Planet(
            20,
            20,
            "Earth",
            "United Nations",
            12345,
            {
                "Food": 2,
            }
        )
    )

    system.planets.append(
        Planet(
            30,
            25,
            "Mars",
            "United Nations",
            67890,
            {
                "Food": 1,
            }
        )
    )

    system.stations.append(
        Station(
            25,
            15,
            "Earth Orbital",
            "United Nations",
            {
                "Food": 2,
            }
        )
    )

    return system

def generate_planet(seed):

    random.seed(seed)

    width = 80
    height = 50

    planet_map = []

    for y in range(height):

        row = []

        for x in range(width):

            roll = random.random()

            if roll < 0.15:
                row.append("^")

            elif roll < 0.35:
                row.append("~")

            else:
                row.append(".")

        planet_map.append(row)

    return planet_map

for i in range(len(STAR_NAMES)):
    stars.append(Star(random.randint(0,WIDTH-1), random.randint(0, HEIGHT-1), STAR_NAMES[i]))

for star in stars:
    if star.name == "Sol":
        star.system = create_sol_system()

def generate_hub(seed):

    random.seed(seed)

    width = 20
    height = 12

    hub = []

    for y in range(height):

        row = []

        for x in range(width):

            if (
                x == 0
                or x == width - 1
                or y == 0
                or y == height - 1
            ):
                row.append("#")
            else:
                row.append(".")

        hub.append(row)

    buildings = ["T", "S", "E", "B"]

    for building in buildings:

        while True:

            x = random.randint(1, width - 2)
            y = random.randint(1, height - 2)

            if hub[y][x] == ".":
                hub[y][x] = building
                break

    return hub

game_state = "STORY"

current_planet = None

planet_player_x = 40
planet_player_y = 25

current_system = None

current_object = None

current_location = None

messages = []

def add_message(text):
    messages.append(text)

    if len(messages) > 10:
        messages.pop(0)

with open("story.txt", "r", encoding="utf-8") as f:
    story_text = f.read()

text_width = 50

wrapped_lines = textwrap.wrap(
    story_text,
    width=text_width
)

text_x = (WIDTH - text_width) // 2
text_y = 4

tileset = tcod.tileset.load_tilesheet(
    "dejavu10x10_gs_tc.png",
    32,
    8,
    tcod.tileset.CHARMAP_TCOD,
)

box_width = WIDTH - 8
box_height = HEIGHT - 8

box_x = (WIDTH - box_width) // 2
box_y = (HEIGHT - box_height) // 2

with tcod.context.new(
    columns=WIDTH,
    rows=HEIGHT,
    title="Space Rogue",
    tileset=tileset,
    sdl_window_flags=tcod.context.SDL_WINDOW_RESIZABLE
) as context:

    while True:
        console.clear()

        if game_state == "STORY":

            for i, line in enumerate(wrapped_lines):
                console.print(
                    text_x,
                    text_y + i,
                    line
                )

            console.print(
                2,
                HEIGHT - 2,
                "Press any key to continue..."
            )

        elif game_state == "GALAXY":

            console.print(
                WIDTH-15,
                HEIGHT-1,
                f"Credits: {credits}"
            )

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

            current_object = None

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

                if (
                    system_player_x == planet.x
                    and
                    system_player_y == planet.y
                ):
                    current_object = planet

            for station in current_system.stations:

                console.print(
                    station.x,
                    station.y,
                    "S"
                )

                if (
                    system_player_x == station.x
                    and
                    system_player_y == station.y
                ):
                    current_object = station

            console.print(
                system_player_x,
                system_player_y,
                "@"
            )

            if current_object:

                console.print(
                    1,
                    HEIGHT - 2,
                    f"Object: {current_object.name}"
                )

                console.print(
                    1,
                    HEIGHT - 3,
                    "ENTER - Visit"
                )

        elif game_state == "PLANET":

            hub = current_planet.hub_map

            for y in range(len(hub)):

                for x in range(len(hub[y])):

                    console.print(
                        x,
                        y,
                        hub[y][x]
                    )

            console.print(
                planet_player_x,
                planet_player_y,
                "@"
            )

        elif game_state == "LOCATION":
            console.print(
                WIDTH // 2 - len(current_location.name) // 2,
                5,
                current_location.name
            )

            console.print(10, 10, "[1] Trading Post")
            console.print(10, 11, "[2] Shipyard")
            console.print(10, 12, "[3] Exchange")
            console.print(10, 13, "[4] Bar")

            console.print(
                10,
                15,
                "ESC - Leave"
            )
        
        elif game_state == "MARKET":
                    
                    food_count = 0

                    for item in inventory.items:
                        if item.name == "Food":
                            food_count += 1

                    console.print(
                        WIDTH // 2 - len(current_location.name) // 2,
                        2,
                        f"{current_location.name} Market"
                    )

                    console.print(
                        2,
                        4,
                        f"Credits: {credits}"
                    )

                    food_price = current_location.market["Food"]

                    console.print(
                        2,
                        8,
                        f"[1] Buy Food ({food_price} credits)"
                    )

                    console.print(
                        2,
                        10,
                        f"[2] Sell Food ({food_price} credits)"
                    )

                    console.print(
                        2,
                        6,
                        f"You own: {food_count} Food"
                    )
                    
                    console.print(
                        2,
                        12,
                        "ESC - Leave"
                    )

        elif game_state == "INVENTORY":
            console.print(
                WIDTH // 2 - 4,
                2,
                "INVENTORY"
            )

            console.print(
                2,
                4,
                f"Cargo: {inventory.used_space()}/{inventory.space}"
            )

            for i, item in enumerate(inventory.items):
                console.print(
                    2,
                    6 + i,
                    item.name
                )

        context.present(console)

        for event in tcod.event.get():
            if isinstance(event, tcod.event.Quit):
                raise SystemExit()

            if isinstance(event, tcod.event.KeyDown):
                
                if event.sym == tcod.event.KeySym.I:
                    previous_state = game_state
                    game_state = "INVENTORY"
                    continue
                
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

                    elif event.sym == tcod.event.KeySym.RETURN:

                        if current_object:

                            current_location = current_object
                            game_state = "LOCATION"
                
                elif game_state == "PLANET":

                    if event.sym == tcod.event.KeySym.UP:
                        planet_player_y -= 1

                    elif event.sym == tcod.event.KeySym.DOWN:
                        planet_player_y += 1

                    elif event.sym == tcod.event.KeySym.LEFT:
                        planet_player_x -= 1

                    elif event.sym == tcod.event.KeySym.RIGHT:
                        planet_player_x += 1

                    elif event.sym == tcod.event.KeySym.ESCAPE:
                        game_state = "SYSTEM"

                elif game_state == "LOCATION":

                    if event.sym == tcod.event.KeySym.ESCAPE:
                        game_state = "SYSTEM"

                    elif event.sym == tcod.event.KeySym.N1:
                        previous_state = game_state
                        game_state = "MARKET"

                elif game_state == "STORY":
                    game_state = "GALAXY"
                    continue

                elif game_state == "MARKET":
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        game_state = previous_state
                    elif event.sym == tcod.event.KeySym.N1:
                        food_price = current_location.market["Food"]

                        if credits >= food_price:
                            if inventory.free_space() >= FOOD.size:

                                credits -= food_price

                                inventory.items.append(FOOD)

                                add_message(
                                    "Bought Food"
                                )
                    elif event.sym == tcod.event.KeySym.N2:
                        for item in inventory.items:
                            if item.name == "Food":
                                inventory.items.remove(item)
                                credits += food_price
                                add_message(
                                    "Sold food"
                                )
                                break

                elif game_state == "INVENTORY":
                    if event.sym == tcod.event.KeySym.ESCAPE:
                        game_state = previous_state