"""Core game object classes: stars, systems, planets, stations, items."""


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


class Item:
    def __init__(self, name, size):
        self.name = name
        self.size = size


class Inventory:
    def __init__(self, space):
        self.space = space
        self.items = []

    def used_space(self):
        return sum(item.size for item in self.items)

    def free_space(self):
        return self.space - self.used_space()


# Shared item instances
FOOD = Item("Food", 2)