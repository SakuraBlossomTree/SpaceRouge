"""Surveying a planet or station from your ship (V while sitting on it).

Costs a little fuel, once per object. It logs a short report and finishes any
active "Site Survey" contract that names the object. Pure logic, no UI.
"""

from core import state

SURVEY_FUEL = 3


def is_gate(obj):
    return hasattr(obj, "destination")


def key(obj):
    return f"{state.current_system.name}|{obj.name}"


def is_surveyed(obj):
    return key(obj) in state.surveyed_objects


def object_at_ship():
    """The planet, station or gate the ship is sitting exactly on, or None."""
    system = state.current_system
    if system is None:
        return None
    pos = (state.system_player_x, state.system_player_y)
    for o in [*system.planets, *system.stations, *system.jump_points]:
        if (o.x, o.y) == pos:
            return o
    return None


def _cheapest_jump():
    from core import travel
    gates = state.current_system.jump_points
    return min((travel.jump_fuel(jp) for jp in gates), default=0)


def can_survey(obj):
    """(ok, reason). Never lets a survey leave you too dry for a gate."""
    if is_gate(obj):
        return False, "gates can't be surveyed"
    if is_surveyed(obj):
        return False, "already surveyed"
    need = SURVEY_FUEL + _cheapest_jump()
    if state.fuel < need:
        return False, f"needs {SURVEY_FUEL} fuel and enough left for a jump"
    return True, ""


def report(obj):
    owner = getattr(obj, "govement", None) or getattr(obj, "faction", "unknown")
    kind = "Planet" if hasattr(obj, "govement") else "Station"
    goods = len(obj.market) if obj.market else 0
    trade = f"trades {goods} goods" if goods else "no market"
    return (f"Survey report: {kind} {obj.name} ({owner}), "
            f"{state.current_system.archetype} system, {trade}.")


def survey_here():
    """The V key: survey whatever you are sitting on."""
    obj = object_at_ship()
    if obj is None:
        state.add_message("Nothing to survey here. Fly onto a planet or station (TAB) and press V.")
        return []
    return survey_object(obj)


def survey_object(obj):
    """Run the survey. Returns the contracts it finished ([] if refused)."""
    from core import missions
    ok, why = can_survey(obj)
    if not ok:
        state.add_message(f"Can't survey {obj.name}: {why}.")
        return []
    state.fuel -= SURVEY_FUEL
    state.surveyed_objects.add(key(obj))
    missions._chart(state.current_system.name)
    state.add_message(report(obj))
    return missions.complete_object_surveys(state.current_system.name, obj.name)
