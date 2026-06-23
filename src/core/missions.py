from __future__ import annotations

import json
from pathlib import Path

class Mission:
    def __init__(self, id , title, description, reward_credits, reward_items, status, source, destination, difficulty):
        self.id = id
        self.title = title
        self.description = description
        self.reward_credits = reward_credits
        self.reward_items = reward_items
        self.status = status
        self.source = source
        self.destination = destination
        self.difficulty = difficulty

        @property
        def is_selectable(self):
            return self.status in ("available", "active")
        
def load_mission(path="missions.json"):
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    missions = []
    for entry in raw["missions"]:
        mission = Mission(
            id=entry["id"],
            title=entry["title"],
            description=entry["description"],
            reward_credits=entry["reward_credits"],
            reward_items=entry["reward_items"],
            status=entry["status"],
            source=entry["source"],
            destination=entry["destination"],
            difficulty=entry["difficulty"],
        )
        missions.append(mission)

    return missions