"""Data classes for simulated networks. A mission builds these; the Session
applies the rules to them."""

from dataclasses import dataclass, field

from hacking.filesystem import NONE, USER, FileSystem


@dataclass
class Vulnerability:
    """Something probe can reveal and breach can exploit.

    challenge: None, or an object with check(answer). When it is set the
    player must supply the answer as the last argument of breach.
    """
    id: str
    name: str
    description: str
    usage: str = ""                 # e.g. "breach {host} token-replay <token>"
    challenge: object = None
    grants: int = USER
    account: str = "service"        # who the player becomes on success
    trace_success: int = 10
    trace_fail: int = 15
    success_text: str = "Exploit succeeded."
    fail_text: str = "Exploit rejected."


@dataclass
class Account:
    username: str
    password: str
    level: int = USER


@dataclass
class Host:
    name: str
    address: str
    description: str = ""
    os: str = "unknown"
    security: int = 1                       # 1 (open) .. 5 (hardened)
    services: list = field(default_factory=list)
    vulnerabilities: list = field(default_factory=list)
    accounts: dict = field(default_factory=dict)      # username -> Account
    filesystem: FileSystem = field(default_factory=FileSystem)
    public_access: int = NONE               # level with no authentication
    probe_cost: int = 3
    denied_penalty: int = 10                # failed `open`
    login_penalty: int = 12                 # failed `login`
    restricted_penalty: int = 5             # touching a restricted path


@dataclass
class Network:
    address: str
    name: str
    banner: list = field(default_factory=list)
    hosts: list = field(default_factory=list)
    scan_cost: int = 3
    trace_interval: float = 10.0   # seconds per +1 trace in real-time mode

    def find(self, key):
        key = (key or "").lower()
        for h in self.hosts:
            if key in (h.name.lower(), h.address.lower()):
                return h
        return None


@dataclass
class Device:
    """The computer the player is sitting at. Home PCs, ship computers,
    portable slates and mission-specific terminals will all be Devices:
    same hacking engine, different files / contacts / installed apps."""
    id: str
    name: str
    kind: str = "mission_terminal"       # home | ship | portable | mission_terminal
    username: str = "pilot"
    os_name: str = "SR-OS 0.1"
    filesystem: FileSystem = field(default_factory=FileSystem)
    contacts: list = field(default_factory=list)       # [(label, address)]
    download_dir: str = "/home/pilot/downloads"
    apps: tuple = ("terminal", "files", "mission")
