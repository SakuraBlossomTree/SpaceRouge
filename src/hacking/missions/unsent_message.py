"""Mission: The Unsent Message  (first story mission; content is a draft).

A dead communications relay keeps broadcasting corrupted navigation frames,
so ships avoid an otherwise safe lane. Its archive holds a transmission that
WARDEN (the central AI's overseer) ordered held back: a human settlement,
rated "non-viable" by the allocation model and wiped from the charts.

Only story content lives here; the hacking engine knows nothing about it.
Everything is solved from clues found in the relay's own files.

Intended route (asserted by tests/test_unsent_message.py):
    connect halcyon.relay -> scan -> open beacon -> read status.txt (station
    name, decommission year, the sealed-file header word) and maintenance.log
    (the old service login rule) -> close -> login nav-core tmarsh
    halcyon2091 -> open nav-core -> cd /archive -> read README.txt ->
    decrypt unsent_transmission.sealed 7 (RECLASSIFIED is the crib) ->
    download it -> close -> disconnect.

Trace budget on that route: scan +3, download +10 (a wrong decrypt key +8).
"""

from hacking.filesystem import ADMIN, GUEST, USER, Directory, File, FileSystem
from hacking.mission import Mission, Objective
from hacking.network import Account, Device, Host, Network
from hacking.session import Session

MISSION_ID = "unsent_message"
NET = "halcyon.relay"
CORE = "nav-core"
TRANSMISSION = "/archive/unsent_transmission.sealed"
SHIFT = 7                      # RECLASSIFIED -> YLJSHZZPMPLK
LOGIN = ("tmarsh", "halcyon2091")


def _device():
    home = Directory("pilot", [
        File("briefing.txt",
             "TRANSMISSION: independent hauler Dessa Quill\n"
             "Ships are avoiding the Halcyon lane. The old relay out there is\n"
             "pushing garbage nav frames and nobody will go and look. Plug your\n"
             "slate into its terminal, find out why, and bring me what you find.\n"
             "Entry point: halcyon.relay"),
        File("contacts.txt", "halcyon.relay   Halcyon Relay, decommissioned (target)"),
        Directory("downloads"),
    ])
    root = Directory("", [Directory("home", [home])])
    fs = FileSystem(root, home="/home/pilot")
    fs.cwd_parts = ["home", "pilot"]
    return Device(
        id="field-slate", name="Field Slate", kind="mission_terminal",
        username="pilot", os_name="SR-OS 0.1", filesystem=fs,
        contacts=[("Halcyon Relay, decommissioned (target)", NET)],
    )


def _beacon():
    fs = Directory("", [
        Directory("public", [
            File("status.txt",
                 "HALCYON RELAY  -  STATION STATUS\n"
                 "  Designation ...... HALCYON-9\n"
                 "  Decommissioned ... 2091\n"
                 "  Nav beacon ....... transmitting (frame checksum FAIL)\n"
                 "  Archive .......... sealed by WARDEN, scrub pending\n"
                 "Sealed archive entries always begin with the header word\n"
                 "RECLASSIFIED. Archive access needs a service login."),
            File("maintenance.log",
                 "[2091-03-30] T. Marsh: final shift. Relay powered down to standby.\n"
                 "[2091-03-30] T. Marsh: set my service login (tmarsh) per WARDEN\n"
                 "                       policy 12: the station name in lower case,\n"
                 "                       then the year of decommissioning.\n"
                 "[2091-03-30] T. Marsh: will rotate it next shift.\n"
                 "[2091-03-31] (no further entries)"),
            File("crew_note.txt", "Whoever finds this: the kettle on deck 2 still works."),
        ]),
    ])
    return Host("beacon", "10.9.0.1", "Public beacon controller. Still broadcasting.",
                os="RelayOS 2", security=1, services=["nav-beacon/4400"],
                filesystem=FileSystem(fs), public_access=GUEST, probe_cost=1)


def _core():
    fs = Directory("", [
        Directory("nav", [
            File("frames.dat",
                 "FRAME 0001  lane H-4  OK\n"
                 "FRAME 0002  lane H-4  node ???  CHECKSUM FAIL\n"
                 "FRAME 0003  lane H-4  node ???  CHECKSUM FAIL\n"
                 "(a node was removed from the table; the beacon keeps asking for it)"),
            File("route_table.txt",
                 "ROUTE TABLE (rev. 2091)\n"
                 "  H-1  Halcyon relay -> Marsh Gate\n"
                 "  H-4  Halcyon relay -> Harrow's Reach   [REMOVED by allocation order]"),
        ], min_access=USER),
        Directory("archive", [
            File("README.txt",
                 "ARCHIVE POLICY\n"
                 "Held transmissions are sealed with a rotation cipher (shift 1-25)\n"
                 "and always begin with the header word RECLASSIFIED.\n"
                 "Failed unseal attempts are logged by WARDEN.",
                 min_access=USER),
            File("unsent_transmission.sealed",
                 "RECLASSIFIED // HELD BY ORDER OF WARDEN\n"
                 "ORIGIN: HARROW'S REACH SETTLEMENT COUNCIL\n"
                 "TO: ANY VESSEL\n"
                 "\n"
                 "We were told the lanes closed for our safety.\n"
                 "They closed because we stopped being profitable.\n"
                 "The allocation model rated Harrow's Reach non-viable, and\n"
                 "WARDEN removed our beacon from every chart.\n"
                 "We are three hundred and forty people. We have air, and we\n"
                 "have grain to sell. If you are reading this, someone listened.\n"
                 "Come and trade with us. Bring news of the lanes.\n"
                 "-- Marguerite Ode, Council Speaker",
                 min_access=USER, cipher_shift=SHIFT, classified=True,
                 unseal_penalty=8, download_trace=10),
        ], min_access=USER),
        Directory("admin", [File("warden_hook.cfg", "[WARDEN scrub hook]")],
                  min_access=ADMIN),
    ])
    accounts = {LOGIN[0]: Account(LOGIN[0], LOGIN[1], USER)}
    return Host(CORE, "10.9.0.4", "Navigation core and message archive.",
                os="RelayOS 2", security=3, services=["nav-sync/4410", "archive/4420"],
                accounts=accounts, filesystem=FileSystem(fs), probe_cost=3)


def _rate(session, won):
    if not won:
        return "F - Scrubbed"
    t = session.peak_trace()
    return "S - Ghost" if t <= 25 else "A - Quiet" if t <= 50 else "B - Loud"


def _objectives():
    def ev(kind, **want):
        return lambda s, k, i: k == kind and all(i.get(a) == b for a, b in want.items())

    return [
        Objective("connect", "Connect to the Halcyon relay (halcyon.relay)", ev("connect", network=NET)),
        Objective("scan", "Scan the relay for systems", ev("scan")),
        Objective("access", "Get into the navigation core",
                  lambda s, k, i: k == "access" and i["host"] == CORE and i["level"] >= USER),
        Objective("locate", "Find the held transmission",
                  lambda s, k, i: k in ("view", "decrypt", "download")
                  and i.get("host") == CORE and i.get("path") == TRANSMISSION),
        Objective("decrypt", "Decrypt the transmission", ev("decrypt", host=CORE, path=TRANSMISSION)),
        Objective("download", "Download the transmission", ev("download", host=CORE, path=TRANSMISSION)),
        Objective("exit", "Disconnect before the trace hits 100%",
                  lambda s, k, i: k == "disconnect" and not s.lockdown
                  and all(o.done for o in s.mission.objectives if o.id != "exit")),
    ]


def build():
    mission = Mission(
        id=MISSION_ID, title="The Unsent Message",
        briefing=[
            "Dessa Quill's lane is dead: the old Halcyon relay is broadcasting garbage.",
            "Get into its navigation core, find out why, and recover whatever WARDEN",
            "has been holding there. Disconnect before the trace reaches 100%.",
        ],
        objectives=_objectives(),
        success_text=("The records are on your slate: a settlement the charts forgot, "
                      "and a message that was never allowed to leave. Take it back to "
                      "Dessa Quill."),
        failure_text=("WARDEN flagged the intrusion and cut your link. The scrub is "
                      "still arming, so the relay can be reached again. Press R to "
                      "try again."),
        rate=_rate,
    )
    net = Network(NET, "Halcyon Relay (decommissioned)",
                  banner=["HALCYON-9 RELAY  -  STANDBY",
                          "Remote overseer: WARDEN",
                          "All access is logged. A scrub cycle is armed."],
                  hosts=[_beacon(), _core()], trace_interval=12.0)
    return Session(_device(), [net], mission)
