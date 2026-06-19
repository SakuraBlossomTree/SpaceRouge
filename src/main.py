import tcod
import random
import time
import textwrap
import math

WIDTH = 80
HEIGHT = 60

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

def twinkle_color(base_color, t, speed=2.0, phase=0.0):
    brightness = (math.sin(t * speed + phase) + 1) / 2
    return tuple(int(c * (0.5 + 0.5 * brightness)) for c in base_color)

credits = 100
inventory = Inventory(20)

FOOD = Item("Food", 2)



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

game_state = "TITLE"

current_planet = None

planet_player_x = 40
planet_player_y = 25

current_system = None

current_object = None

current_location = None

current_star = None

messages = []

def add_message(text):
    messages.append(text)

    if len(messages) > 10:
        messages.pop(0)

with open("story.txt", "r", encoding="utf-8") as f:
    story_text = f.read()

f.close()

text_width = 65
text_x = 6
text_y = 8

with open("title.txt", "r", encoding="utf-8") as f:
    title_text = f.read()

f.close()

tileset = tcod.tileset.load_tilesheet("Haberdash_curses_12x12.png", 16, 16, tcod.tileset.CHARMAP_CP437)

# tileset = tcod.tileset.load_truetype_font("Ubuntu-Regular.ttf", 25, 25)

box_width = WIDTH - 8
box_height = HEIGHT - 8

box_x = (WIDTH - box_width) // 2
box_y = (HEIGHT - box_height) // 2

story_char_index = 0
last_story_time = time.time()

SPIN_FRAMES = ["-", "\\", "|", "/"]

def get_spin_frame(t, speed=8.0, phase=0.0):
    index = int((t * speed + phase)) % len(SPIN_FRAMES)
    return SPIN_FRAMES[index]

RAIN_DROPS = []
RAIN_COUNT = 60
RAIN_CHARS = ["|", "'", "."]

def init_rain():
    drops = []
    for _ in range(RAIN_COUNT):
        drops.append({
            "x": random.randint(0, WIDTH - 1),
            "y": random.uniform(0, HEIGHT - 1),
            "speed": random.uniform(8.0, 20.0),
            "char": random.choice(RAIN_CHARS),
        })
    return drops

RAIN_DROPS = init_rain()

last_rain_time = time.time()

def update_rain(dt):
    for drop in RAIN_DROPS:
        drop["y"] += drop["speed"] * dt
        if drop["y"] >= HEIGHT:
            drop["y"] = 0
            drop["x"] = random.randint(0, WIDTH - 1)
            drop["speed"] = random.uniform(8.0, 20.0)
            drop["char"] = random.choice(RAIN_CHARS)

def draw_rain(console):
    for drop in RAIN_DROPS:
        y = int(drop["y"])
        if 0 <= y < HEIGHT:
            # fade based on speed - faster drops look "closer", brighter
            brightness = int(100 + (drop["speed"] / 20.0) * 100)
            color = (brightness, brightness, min(255, brightness + 30))
            console.print(drop["x"], y, drop["char"], fg=color)

with tcod.context.new(
    columns=WIDTH,
    rows=HEIGHT,
    title="Space Rogue",
    tileset=tileset,
    sdl_window_flags=tcod.context.SDL_WINDOW_RESIZABLE
) as context:

    while True:
        console.clear()

        now = time.time()
        dt = now - last_rain_time
        last_rain_time = now

        update_rain(dt)

        if game_state == "TITLE":

            draw_rain(console)

            console.print(
                10,
                10,
                text=title_text
            )

            console.print(
                WIDTH // 2 - len("Press Enter to start a New Game") // 2,
                24,
                text="Press Enter to start a New Game"
            )

        if game_state == "STORY":

            if (
                story_char_index < len(story_text)
                and
                time.time() - last_story_time > 0.03
            ):
                story_char_index += 1
                last_story_time = time.time()

            visible_text = story_text[:story_char_index]

            wrapped_lines = textwrap.wrap(
                visible_text,
                width=65
            )

            for i, line in enumerate(wrapped_lines):
                console.print(
                    text_x,
                    text_y + (i * 2),
                    line
                )

            if (
                story_char_index < len(story_text)
                and
                int(time.time() * 2) % 2
            ):

                if wrapped_lines:
                    console.print(
                        text_x + len(wrapped_lines[-1]),
                        text_y + ((len(wrapped_lines) - 1) * 2),
                        "_"
                    )

                else:

                    console.print(
                        text_x,
                        text_y,
                        "_"
                    )

            console.print(
                2,
                HEIGHT - 2,
                "SPACE - Skip    ENTER - Continue"
            )

        elif game_state == "GALAXY":

            console.print(
                WIDTH-15,
                HEIGHT-1,
                f"Credits: {credits}"
            )

            on_star = False

            for star in stars:

                t = time.time()
                for i, star in enumerate(stars):
                    color = twinkle_color((255, 255, 0), t, speed=5.0, phase=i*1.3)
                    console.print(star.x, star.y,"*", fg=color) 
                
                if player_x == star.x and player_y == star.y:
                    on_star = True
                    current_star = star

                console.print(current_star.x,current_star.y, "@", fg=(255,255,255))

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

                t = time.time()
                frame = get_spin_frame(t, speed=8.0, phase=3)
                console.print(station.x, station.y, frame, fg=(255, 255, 255))

                if (
                    system_player_x == station.x
                    and
                    system_player_y == station.y
                ):
                    current_object = station

                

            console.print(
                system_player_x,
                system_player_y,
                "@",
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

                if game_state == "TITLE":
                    if event.sym == tcod.event.KeySym.RETURN:
                        game_state = "STORY"
                
                if event.sym == tcod.event.KeySym.I:
                    previous_state = game_state
                    game_state = "INVENTORY"
                    continue

                elif game_state == "STORY":
                    if event.sym == tcod.event.KeySym.SPACE:
                        story_char_index = len(story_text)
                    elif event.sym == tcod.event.KeySym.RETURN:
                        if story_char_index >= len(story_text):
                            current_star = stars[0]
                            current_system = stars[0].system
                            game_state = "SYSTEM"
                
                elif game_state == "GALAXY":

                    if event.sym == tcod.event.KeySym.M:
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

                    elif event.sym == tcod.event.KeySym.M:
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

                