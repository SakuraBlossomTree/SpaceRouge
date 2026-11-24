"""Procedural hacking jobs: data nodes, job boards, rewards and heat.

* About one system in four is a data node (seeded, weighted by archetype). Its
  stations carry a terminal that posts 4-6 jobs a day, listed on the Missions
  Board under the Hacking category.
* With the Hacker Deck (shipyard) you can open the board of any node within
  DECK_RANGE jumps from any dock.
* A job is a seeded network built by hacking/missions/procedural.py. Success
  pays credits; a failure locks that node's terminal until the next day.
* Dirty work builds "heat" (not used for anything yet: it is the hook for a
  later police system). It cools off by 1 every 2 days.
"""

import random
import zlib
from dataclasses import dataclass

from core import state
from hacking.missions import procedural

DECK_RANGE = 2
JOBS_MIN, JOBS_MAX = 4, 6
NODE_CHANCE = {"Research": 0.40, "Trade Hub": 0.35, "Military": 0.25, "Industrial": 0.22,
               "Frontier": 0.20, "Mining": 0.12, "Agricultural": 0.10}
DEFAULT_NODE_CHANCE = 0.18
TIER2_CHANCE = {"Research": 0.6, "Military": 0.6, "Trade Hub": 0.5}
DEFAULT_TIER2 = 0.3
HEAT_FAIL, HEAT_LOUD, HEAT_QUIET = 15, 6, 2
HEAT_COOL_DAYS = 2

_node_cache = {}
_near_cache = {}


@dataclass
class Job:
    key: str
    system: str
    tier: int
    seed: int
    title: str
    company: str
    blurb: str
    reward: int

    @property
    def mission_id(self):
        return procedural.make_id(self.tier, self.seed)


def _rng(*parts):
    return random.Random(zlib.crc32("|".join(str(p) for p in parts).encode()))


def has_deck():
    return state.upgrades.get("hackdeck", 0) > 0


# --------------------------------------------------------------- nodes
def _has_terminal(station):
    """Earth keeps its prototype terminal; the relay's is the story's."""
    from core import story_relay
    return not (story_relay.is_relay(station) or station.name.startswith("Earth"))


def is_node(star):
    """Is this a data node? Needs a (live) station for the terminal."""
    from core import story_relay
    key = (state.galaxy_seed, len(state.stars))
    if _node_cache.get("key") != key:
        _node_cache.clear()
        _node_cache["key"] = key
        _near_cache.clear()
    if star.name in _node_cache:
        return _node_cache[star.name]
    stations = [s for s in star.system.stations if _has_terminal(s)]
    ok = bool(stations) and not (state.relay and state.relay.get("system") == star.name)
    if ok:
        chance = NODE_CHANCE.get(star.system.archetype, DEFAULT_NODE_CHANCE)
        ok = _rng(state.galaxy_seed, "node", star.name).random() < chance
    _node_cache[star.name] = ok
    return ok


def node_names():
    return [s.name for s in state.stars if is_node(s)]


def _star(name):
    return next((s for s in state.stars if s.name == name), None)


def _nearby_nodes(start):
    """[(jumps, star)] of data nodes within DECK_RANGE jumps of `start`."""
    is_node(state.stars[0]) if state.stars else None        # refresh caches
    ck = ("near", start)
    if ck in _near_cache:
        return _near_cache[ck]
    seen, frontier, found = {start}, [start], []
    for depth in range(DECK_RANGE + 1):
        nxt = []
        for name in frontier:
            star = _star(name)
            if star is None:
                continue
            if is_node(star):
                found.append((depth, star))
            for jp in star.system.jump_points:
                if jp.destination not in seen:
                    seen.add(jp.destination)
                    nxt.append(jp.destination)
        frontier = nxt
    found.sort(key=lambda t: (t[0], t[1].name))
    _near_cache[ck] = found
    return found


def board(loc=None):
    """(star, 'terminal' | 'deck') whose job board `loc` can open, or None."""
    from core import story_relay
    loc = loc or state.current_location
    here = state.current_star
    if loc is None or here is None or story_relay.is_relay(loc) or loc.name.startswith("Earth"):
        return None
    is_station = loc in here.system.stations
    if is_station and is_node(here) and _has_terminal(loc):
        return here, "terminal"
    if has_deck():
        near = _nearby_nodes(here.name)
        if near:
            return near[0][1], "deck"
    return None


# --------------------------------------------------------------- jobs
def jobs(star, day=None):
    day = state.day if day is None else day
    rng = _rng(state.galaxy_seed, "jobs", star.name, day)
    t2 = TIER2_CHANCE.get(star.system.archetype, DEFAULT_TIER2)
    out = []
    for i in range(rng.randint(JOBS_MIN, JOBS_MAX)):
        tier = 2 if rng.random() < t2 else 1
        seed = rng.randrange(10 ** 6)
        reward = (110 if tier == 1 else 220) + 5 * rng.randrange(0, 19 if tier == 1 else 19)
        title, co, blurb = procedural.describe(tier, seed)
        out.append(Job(f"{star.name}|{day}|{i}", star.name, tier, seed, title, co, blurb, reward))
    return out


def status(job):
    return state.hack_done.get(job.key)           # None | "done" | "failed"


def locked_until(star_name):
    """Day number the node is locked through, or None."""
    d = state.hack_lock.get(star_name)
    return d if d is not None and state.day <= d else None


def available(job):
    return status(job) is None and locked_until(job.system) is None


def count_available(star):
    return sum(1 for j in jobs(star) if available(j))


def board_missions(loc=None):
    """The jobs as Mission-shaped rows for the Missions Board's Hacking tab.
    They are display objects only (never saved): `.job` holds the real job."""
    from core.missions import Mission
    found = board(loc)
    if found is None:
        return []
    star, via = found
    locked = locked_until(star.name)
    rows = []
    for job in jobs(star):
        st = status(job)
        status_ = ("completed" if st == "done" else "failed" if st == "failed"
                   else "locked" if locked is not None else "available")
        how = ("Harder: crack a staff password first. " if job.tier > 1
               else "Easier: a leak is waiting to be found. ")
        desc = (f"{job.blurb[:1].upper()}{job.blurb[1:]}. {how}"
                "One attempt: if the trace hits 100% the terminal locks until tomorrow.")
        if locked is not None and st is None:
            desc = f"The {star.name} terminal is locked until day {locked + 1}. " + desc
        m = Mission(job.key, job.title, desc, "hackjob", job.reward, [], status_,
                    (loc or state.current_location).name,
                    f"{star.name} {'terminal' if via == 'terminal' else 'via deck'}",
                    job.tier + 1, dest_system=star.name, source_system=star.name,
                    key=job.key)
        m.job = job
        rows.append(m)
    return rows


# --------------------------------------------------------------- heat
def heat():
    cooled = max(0, state.day - state.heat_day) // HEAT_COOL_DAYS
    return max(0, state.heat - cooled)


def add_heat(amount):
    state.heat = heat() + amount
    state.heat_day = state.day
    state.heat = min(100, state.heat)


# --------------------------------------------------------------- running a job
_running = {}          # mission id -> Job
_handled = None


def start(job):
    from core import computer_input
    _running[job.mission_id] = job
    computer_input.open_computer(job.mission_id, back_to="LOCATION")


def on_computer_update(computer):
    """Per-frame check (computer_input.update): settle a finished job once."""
    global _handled
    m = getattr(computer, "mission", None)
    mid = getattr(computer, "mission_id", None)
    if not procedural.is_job(mid) or m is None or not m.finished or m is _handled:
        return
    _handled = m
    job = _running.get(mid)
    if job is None or job.key in state.hack_done:
        return
    if m.status == "success":
        state.hack_done[job.key] = "done"
        state.credits += job.reward
        peak = m.result.get("trace", 0)
        add_heat(HEAT_QUIET if peak <= 35 else HEAT_LOUD)
        state.add_message(f"Job done: {job.title}. The broker pays {job.reward} credits.")
    else:
        state.hack_done[job.key] = "failed"
        state.hack_lock[job.system] = state.day
        add_heat(HEAT_FAIL)
        state.add_message(f"Job failed: {job.title}. The {job.system} terminal is "
                          "locked until tomorrow, and your name is going round.")
