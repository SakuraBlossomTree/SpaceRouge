import pathlib, sys

ROOT = pathlib.Path(".")

def patch(rel, pairs):
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{rel}: expected 1 match, found {n}:\n{old[:120]}")
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8", newline="\n")
    print("patched", rel)

# ---- missions: stable keys, source system, skip completed ------------------
patch("src/core/missions.py", [
(
'''                 cargo=None, amount=None, systems_to_visit=None, dest_system=None):
        self.id = id''',
'''                 cargo=None, amount=None, systems_to_visit=None, dest_system=None,
                 source_system=None, key=None):
        self.id = id
        self.source_system = source_system   # system the mission was posted in
        self.key = key                       # stable across regeneration'''),
(
'''def generate_missions(location, current_system, all_stars, count=4):''',
'''def generate_missions(location, current_system, all_stars, count=4, completed=()):'''),
(
'''                difficulty=difficulty,
            ))

        elif mission_type == "survey":''',
'''                difficulty=difficulty,
                source_system=current_system.name,
            ))

        elif mission_type == "survey":'''),
(
'''                systems_to_visit=systems_to_visit,
            ))''',
'''                systems_to_visit=systems_to_visit,
            ))'''),
(
'''            ))

        elif mission_type == "bounty":''',
'''            ))

        elif mission_type == "bounty":'''),
(
'''            ))

    return missions''',
'''            ))

    # Keys are stable (same place, same slot), so a contract the player has
    # already finished is never posted again.
    for idx, m in enumerate(missions):
        m.key = f"{location.name}|{current_system.name}|{idx}"
    return [m for m in missions if m.key not in completed]'''),
])

# ---- state / newgame ---------------------------------------------------------
patch("src/core/state.py", [(
'''missions = []
visible_missions = []
selected_mission_index = 0
''',
'''missions = []
visible_missions = []
selected_mission_index = 0
completed_mission_keys = set()   # contracts finished this galaxy; never reposted
''')])
patch("src/core/newgame.py", [(
'''    state.missions = []
''',
'''    state.missions = []
    state.completed_mission_keys = set()
''')])

# ---- travel: hard-mode price multiplier + route fuel estimate ---------------
patch("src/core/travel.py", [
(
'''def toggle_difficulty():''',
'''HARD_PRICE_MULTIPLIER = 3.0   # Hard: market prices are up to 3x the economy's own


def adjust_price(price):
    """The price the player sees and pays: Hard mode multiplies it by 3."""
    return int(round(price * HARD_PRICE_MULTIPLIER)) if hard() else price


def toggle_difficulty():'''),
(
'''    a, b = _star(jp.source), _star(jp.destination)
    if a is None or b is None:
        return 5
    return 3 + round(math.hypot(a.x - b.x, a.y - b.y) / 3)''',
'''    a, b = _star(jp.source), _star(jp.destination)
    if a is None or b is None:
        return 5
    return gate_fuel(a, b)


def gate_fuel(a, b):
    """Fuel for one jump gate between two star systems (easy-mode rule)."""
    return 3 + round(math.hypot(a.x - b.x, a.y - b.y) / 3)


def route_estimate(stars, here, there):
    """(jumps, fuel) for the fewest-jump gate route from system `here` to
    `there`, or None if unreachable. Fuel is None in Hard mode, where
    flying (not jumping) burns fuel and no fixed figure applies."""
    by_name = {s.name: s for s in stars}
    if here not in by_name or there not in by_name:
        return None
    parent = {here: None}
    frontier = [here]
    while frontier and there not in parent:
        nxt = []
        for name in frontier:
            for jp in by_name[name].system.jump_points:
                if jp.destination in by_name and jp.destination not in parent:
                    parent[jp.destination] = name
                    nxt.append(jp.destination)
        frontier = nxt
    if there not in parent:
        return None
    path, cur = [], there
    while parent[cur] is not None:
        path.append((parent[cur], cur))
        cur = parent[cur]
    jumps = len(path)
    if hard():
        return jumps, None
    fuel = sum(gate_fuel(by_name[a], by_name[b]) for a, b in path)
    return jumps, fuel'''),
])

# ---- market screen: show the adjusted prices ---------------------------------
patch("src/render/market.py", [
(
'''from core import state
''',
'''from core import state, travel
'''),
])
p = ROOT / "src/render/market.py"
t = p.read_text(encoding="utf-8")
assert t.count("        price = loc.market[name]\n") == 2
t = t.replace("        price = loc.market[name]\n", "        price = travel.adjust_price(loc.market[name])\n")
old_base = "        base = ec.avg_price(name) if ec else BASE_PRICES.get(name, price)\n"
assert t.count(old_base) == 1
t = t.replace(old_base, "        base = travel.adjust_price(ec.avg_price(name)) if ec else BASE_PRICES.get(name, price)\n")
old_prev = "        prev = ms.prev.get(name, price) if ms else price\n"
assert t.count(old_prev) == 1
t = t.replace(old_prev, "        prev = travel.adjust_price(ms.prev.get(name, loc.market[name])) if ms else price\n")
p.write_text(t, encoding="utf-8", newline="\n")
print("patched src/render/market.py (prices)")

# ---- events: buy/sell at adjusted price, contract cargo tagging, completion --
p = ROOT / "src/core/events.py"
t = p.read_text(encoding="utf-8")
def rep(old, new, count=1):
    global t
    n = t.count(old)
    if n != count:
        sys.exit(f"events.py: expected {count} match(es), found {n}:\n{old[:120]}")
    t = t.replace(old, new)

rep("    price = state.current_location.market[name]\n",
    "    price = travel.adjust_price(state.current_location.market[name])\n", count=2)

rep("""    existing_sources = {m.source for m in state.missions if m.status == "available"}

    if state.current_location.name not in existing_sources:
        new_missions = generate_missions(
            state.current_location,
            state.current_system,
            state.stars,
            count=4,
        )""",
"""    existing_sources = {m.source for m in state.missions if m.status == "available"}

    if state.current_location.name not in existing_sources:
        new_missions = generate_missions(
            state.current_location,
            state.current_system,
            state.stars,
            count=4,
            completed=state.completed_mission_keys,
        )""")

rep("""                for _ in range(mission.amount):
                    state.inventory.items.append(item)
""",
"""                # Tag each unit with where it came from, so only this
                # contract's cargo can be handed in for it.
                for _ in range(mission.amount):
                    state.inventory.items.append(entities.Item(
                        item.name, item.size,
                        origin_system=mission.source_system,
                        mission_key=mission.key))
""")

rep("""                carried = sum(1 for i in state.inventory.items if i.name == item.name)
""",
"""                carried = sum(1 for i in state.inventory.items if i.mission_key == mission.key)
""")

rep("""                for cargo_item in list(state.inventory.items):
                    if cargo_item.name == item.name and removed < mission.amount:""",
"""                for cargo_item in list(state.inventory.items):
                    if cargo_item.mission_key == mission.key and removed < mission.amount:""")

rep("""            mission.status = "completed"
""",
"""            mission.status = "completed"
            state.completed_mission_keys.add(mission.key)
""")
p.write_text(t, encoding="utf-8", newline="\n")
print("patched src/core/events.py")

# ---- galaxy preview: autopilot fuel when the scanner covers the system -------
patch("src/render/galaxy.py", [(
'''    if contracts:
        rows.append(("Contracts here", str(contracts), ui.KEY))
    return rows''',
'''    if contracts:
        rows.append(("Contracts here", str(contracts), ui.KEY))
    if not here and here_name and view.scanner_covers(star, stars):
        from core import travel
        est = travel.route_estimate(stars, here_name, star.name)
        if est is None:
            rows.append(("Autopilot fuel", "no route", ui.BAD))
        else:
            jumps, fuel = est
            text = (f"~{fuel} fuel" if fuel is not None else "varies (Hard)")
            rows.append(("Autopilot fuel", f"{text}, {jumps} jump{'s' if jumps != 1 else ''}", ui.KEY))
    return rows'''),
])
patch("src/render/hud.py", [(
'''            for i, (k, v, fg) in enumerate(preview_rows(star, state.stars)[:5]):''',
'''            for i, (k, v, fg) in enumerate(preview_rows(star, state.stars)[:6]):''')])
