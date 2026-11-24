"""Security trace: a 0-100 meter that rises when the player does something
the remote system can notice. Every rise is a fixed number chosen by the
rules (never random), is printed with its reason, and crossing a threshold
prints a warning. At 100 the remote system locks the connection down."""

from hacking.output import Out, trace_line, warn, alert

LIMIT = 100

# (threshold, label, builder, message)
THRESHOLDS = (
    (25, "NOTICED", warn, "WARDEN: anomalous traffic logged from your address."),
    (50, "ALERT", warn, "WARDEN: intrusion heuristics triggered. Trace is climbing."),
    (75, "CRITICAL", alert, "WARDEN: ACTIVE TRACE IN PROGRESS. Disconnect soon!"),
    (100, "LOCKDOWN", alert, "WARDEN: INTRUDER LOCATED. CONNECTION SEVERED."),
)


def level_name(value):
    name = "CLEAR"
    for limit, label, _, _ in THRESHOLDS:
        if value >= limit:
            name = label
    return name


class Trace:
    def __init__(self, limit=LIMIT):
        self.limit = limit
        self.value = 0

    @property
    def locked(self):
        return self.value >= self.limit

    @property
    def level(self):
        return level_name(self.value)

    @property
    def pct(self):
        return min(100, int(100 * self.value / self.limit))

    def add(self, amount, reason):
        """Raise the trace. Returns the lines to print (reason + warnings)."""
        before = self.value
        self.value = min(self.limit, self.value + amount)
        lines = [trace_line(f"[TRACE +{amount}] {reason}  ({self.value}%)")]
        for limit, _, builder, message in THRESHOLDS:
            if before < limit <= self.value:
                lines.append(builder(message))
        return lines
