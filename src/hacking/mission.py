"""Mission tracking: objectives that complete on session events, plus a
win / fail state. Content (texts, objective rules) lives in missions/."""

from dataclasses import dataclass, field
from typing import Callable

from hacking.output import ok, alert


@dataclass
class Objective:
    id: str
    text: str
    match: Callable            # match(session, kind, info) -> bool
    done: bool = False


@dataclass
class Mission:
    id: str
    title: str
    briefing: list
    objectives: list
    success_text: str = "Mission complete."
    failure_text: str = "Mission failed."
    status: str = "active"     # active | success | failed
    rate: Callable = None      # rate(session, won) -> short rating string
    result: dict = field(default_factory=dict)

    @property
    def finished(self):
        return self.status != "active"

    def progress(self):
        return sum(o.done for o in self.objectives), len(self.objectives)

    def on_event(self, session, kind, info):
        """Called by the session for every notable event. Returns lines."""
        if self.finished:
            return []
        lines = []
        for o in self.objectives:
            if not o.done and o.match(session, kind, info):
                o.done = True
                lines.append(ok(f"[OBJECTIVE COMPLETE] {o.text}"))
        if kind == "lockdown":
            self._finish(session, False)
            lines.append(alert("*** MISSION FAILED: you were detected ***"))
        elif all(o.done for o in self.objectives):
            self._finish(session, True)
            lines.append(ok("*** MISSION COMPLETE ***"))
        return lines

    def _finish(self, session, won):
        self.status = "success" if won else "failed"
        trace = session.peak_trace()
        self.result = {
            "won": won,
            "trace": trace,
            "commands": session.commands_run,
            "rating": self.rate(session, won) if self.rate else ("PASS" if won else "FAIL"),
            "objectives": self.progress(),
        }
