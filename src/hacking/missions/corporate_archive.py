"""Mission: Corporate Archive Breach  (PROTOTYPE CONTENT - not canon lore).

Everything story-related is isolated in this file and meant to be replaced
when the real narrative exists. The hacking engine knows nothing about it.

Intended route (also asserted by tests/test_hacking.py):
    connect helix.net -> scan -> open gateway -> read the public files
    (staff login + password format) -> login mail r.vance orbit2291 ->
    open mail -> read r.vance's archive_sync.log (leaked session token) ->
    probe archive-07 -> breach archive-07 token-replay <token> ->
    open archive-07 -> cd /vault -> read README.txt (all sealed files start
    with CLASSIFIED) -> decrypt the dossier (shift 11) -> download ->
    close -> disconnect.
A loud shortcut exists: breach archive-07 ftp-overflow (+40 trace).
"""

from hacking.filesystem import ADMIN, GUEST, USER, Directory, File, FileSystem
from hacking.mission import Mission, Objective
from hacking.network import Account, Device, Host, Network, Vulnerability
from hacking.puzzles import SecretChallenge
from hacking.session import Session

NET = "helix.net"
ARCHIVE = "archive-07"
DOSSIER = "/vault/lantern_dossier.sealed"
TOKEN = "HX-7F3A-92C1"
SHIFT = 11


def _device():
    home = Directory("pilot", [
        File("briefing.txt",
             "CLIENT BRIEF (anonymous broker)\n"
             "HelixCorp keeps a classified dossier, PROJECT LANTERN, on a cold-storage\n"
             "archive run by their security AI, WARDEN. Get in, find it, unseal it,\n"
             "pull it, and get out before WARDEN finishes tracing you.\n"
             "Entry point: helix.net"),
        File("contacts.txt", "helix.net   HelixCorp secure gateway (target)"),
        Directory("downloads"),
    ])
    root = Directory("", [Directory("home", [home])])
    fs = FileSystem(root, home="/home/pilot")
    fs.cwd_parts = ["home", "pilot"]
    return Device(
        id="field-slate", name="Field Slate", kind="mission_terminal",
        username="pilot", os_name="SR-OS 0.1",
        filesystem=fs,
        contacts=[("HelixCorp secure gateway (target)", NET)],
    )


def _gateway():
    fs = Directory("", [
        Directory("public", [
            File("welcome.txt",
                 "Welcome to the HelixCorp public gateway.\n"
                 "Staff: see staff_directory.txt. IT: see it_notice.txt."),
            File("staff_directory.txt",
                 "HELIXCORP STAFF DIRECTORY (public extract)\n"
                 "  login       name             dept          joined\n"
                 "  r.vance     Dr. Rhea Vance   Archive Ops   2291\n"
                 "  t.okafor    T. Okafor        Logistics     2288\n"
                 "  m.ibarra    M. Ibarra        Facilities    2293\n"
                 "\n"
                 "OFFICE PET DAY ROSTER (wellness programme, public)\n"
                 "  Dr. Vance .... Orbit (cat)\n"
                 "  T. Okafor .... Biscuit (dog)\n"
                 "  M. Ibarra .... Nova (parrot)"),
            File("it_notice.txt",
                 "IT NOTICE #447\n"
                 "After the WARDEN audit, staff mail passwords follow one format:\n"
                 "  <pet name in lower case><year you joined>\n"
                 "Rotate your old password within 30 days. Do not share it."),
        ]),
        Directory("staff", [File("payroll.dat", "[ledger data omitted]", min_access=USER)],
                  min_access=USER),
    ])
    return Host("gateway", "10.4.0.1", "Public web portal and DNS for HelixCorp.",
                os="HX-Linux 4", security=1, services=["https/443", "dns/53"],
                filesystem=FileSystem(fs), public_access=GUEST, probe_cost=1)


def _mail():
    fs = Directory("", [
        Directory("spool", [
            Directory("r.vance", [
                File("inbox.txt", "From: facilities\nSubject: Pet Day was a success!\n"
                                  "Thanks to everyone who brought an animal in."),
                File("archive_sync.log",
                     "[2291-11-02 03:00] archive-07: nightly sync started\n"
                     "[2291-11-02 03:00] auth-daemon: handshake ok, svc-archiver\n"
                     f"[2291-11-02 03:01] auth-daemon: session token {TOKEN}\n"
                     "[2291-11-02 03:01] WARNING: token not bound to client address\n"
                     "                   (replay possible, ticket SEC-3391 still open)\n"
                     "[2291-11-02 03:09] archive-07: sync complete"),
            ]),
            Directory("t.okafor", [
                File("lunch.txt", "Anyone up for noodles on deck 4?"),
            ]),
        ]),
        Directory("admin", [File("filters.cfg", "# spam filter rules")], min_access=ADMIN),
    ])
    accounts = {"r.vance": Account("r.vance", "orbit2291", USER),
                "t.okafor": Account("t.okafor", "biscuit2288", USER)}
    return Host("mail", "10.4.0.12", "Staff mail relay and mailbox store.",
                os="HX-Linux 4", security=2, services=["smtp/25", "imap/143"],
                accounts=accounts, filesystem=FileSystem(fs), probe_cost=4)


def _hr():
    return Host("hr-db", "10.4.0.20", "Personnel database. Heavily guarded and irrelevant.",
                os="HX-Linux 4", security=4, services=["sql/5432"],
                filesystem=FileSystem(Directory("", [File("people.db", "[locked]")])),
                probe_cost=4, denied_penalty=10)


def _archive():
    fs = Directory("", [
        Directory("vault", [
            File("README.txt",
                 "VAULT POLICY\n"
                 "Sealed documents use a rotation cipher (shift 1-25) and always\n"
                 "begin with the standard header word CLASSIFIED.\n"
                 "Failed unseal attempts are logged by WARDEN.",
                 min_access=USER),
            File("inventory_2290.csv", "item,qty\ncoolant,40\nfilters,12", min_access=USER),
            File("lantern_dossier.sealed",
                 "CLASSIFIED // EYES ONLY\n"
                 "PROJECT LANTERN - DOSSIER 7\n"
                 "Prototype placeholder text. Replace with real story content.\n"
                 "Helix engineers hid a navigation beacon in the Kessel Drift\n"
                 "and have been trading with whoever answers its signal.",
                 min_access=USER, cipher_shift=SHIFT, classified=True,
                 unseal_penalty=8, download_trace=10),
        ], min_access=USER),
        Directory("admin", [File("warden_core.cfg", "[WARDEN core settings]")], min_access=ADMIN),
    ])
    vulns = [
        Vulnerability(
            "token-replay", "Session token replay",
            "auth-daemon accepts a captured session token from any address.",
            usage="breach {host} token-replay <token>",
            challenge=SecretChallenge(TOKEN, case_sensitive=False),
            account="svc-archiver", grants=USER, trace_success=10, trace_fail=15,
            success_text="Token accepted. auth-daemon trusts the replayed session.",
            fail_text="auth-daemon rejected the token."),
        Vulnerability(
            "ftp-overflow", "vault-ftp buffer overflow",
            "Crashes the FTP daemon into a root-less shell. Extremely loud.",
            usage="breach {host} ftp-overflow",
            account="ftp-shell", grants=USER, trace_success=40,
            success_text="Overflow succeeded. vault-ftp spawned a shell."),
    ]
    return Host(ARCHIVE, "10.4.0.77", "AI-managed cold archive. Access is brokered by WARDEN.",
                os="WARDEN-OS", security=4, services=["vault-ftp/990", "auth-daemon/7007"],
                vulnerabilities=vulns, filesystem=FileSystem(fs), probe_cost=4)


def _rate(session, won):
    if not won:
        return "F - Detected"
    t = session.peak_trace()
    return "S - Ghost" if t <= 35 else "A - Quiet" if t <= 60 else "B - Loud"


def _objectives():
    def ev(kind, **want):
        return lambda s, k, i: k == kind and all(i.get(a) == b for a, b in want.items())

    return [
        Objective("connect", "Connect to the HelixCorp network (helix.net)", ev("connect", network=NET)),
        Objective("scan", "Scan the network for systems", ev("scan")),
        Objective("probe", "Find a vulnerability on the archive server", ev("probe", host=ARCHIVE)),
        Objective("access", "Gain access to the archive server",
                  lambda s, k, i: k == "access" and i["host"] == ARCHIVE and i["level"] >= USER),
        Objective("locate", "Locate the classified dossier",
                  lambda s, k, i: k in ("view", "decrypt", "download")
                  and i.get("host") == ARCHIVE and i.get("path") == DOSSIER),
        Objective("decrypt", "Decrypt the dossier", ev("decrypt", host=ARCHIVE, path=DOSSIER)),
        Objective("download", "Download the dossier", ev("download", host=ARCHIVE, path=DOSSIER)),
        Objective("exit", "Disconnect before the trace hits 100%",
                  lambda s, k, i: k == "disconnect" and not s.lockdown
                  and all(o.done for o in s.mission.objectives if o.id != "exit")),
    ]


def build():
    mission = Mission(
        id="corporate_archive", title="Corporate Archive Breach",
        briefing=[
            "A broker sent word of a classified archive on HelixCorp's AI-run network.",
            "Infiltrate it, locate the Project Lantern dossier, decrypt it, download it,",
            "and disconnect before WARDEN's security trace reaches 100%.",
        ],
        objectives=_objectives(),
        success_text="You slipped out with the Lantern dossier. WARDEN never found you.",
        failure_text="WARDEN traced you and cut the link. The dossier stays sealed.",
        rate=_rate,
    )
    net = Network(NET, "HelixCorp Secure Network",
                  banner=["HELIXCORP SECURE GATEWAY v9.2",
                          "Autonomous security overseer: WARDEN",
                          "All access is logged. Unauthorized activity will be traced."],
                  hosts=[_gateway(), _mail(), _hr(), _archive()])
    return Session(_device(), [net], mission)
