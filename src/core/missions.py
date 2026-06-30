from __future__ import annotations

import json
from pathlib import Path

class Mission:
    def __init__(self, id , title, description, mission_type, reward_credits, reward_items, status, source, destination, difficulty,cargo=None, amount=None):
        self.id = id
        self.title = title
        self.mission_type = mission_type
        self.description = description
        self.reward_credits = reward_credits
        self.reward_items = reward_items
        self.status = status
        self.source = source
        self.destination = destination
        self.difficulty = difficulty
        self.cargo = cargo
        self.amount = amount

        @property
        def is_selectable(self):
            return self.status in ("available", "active")
        
def load_mission(path="missions.json"):
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    missions = []
    for entry in raw["missions"]:
        mission = Mission(**entry)
        missions.append(mission)
        
    return missions