"""Render the HELP overlay: the Pilot's Handbook (paged reference)."""

from core import state
from render import ui

W, H = 72, 46

# ---------------------------------------------------------------------------
# Live numbers: anything that can change in the code is read from the code
# ---------------------------------------------------------------------------

def _goal():
    from core import debt
    return ("You fly the Rogue, a light hauler bought on a "
            f"{state.starting_debt:,} credit loan. Trade, run contracts and pay "
            f"the loan off within {debt.loan_days()} days.")


def _loan_deadline():
    from core import debt
    return (f"You have {debt.loan_days()} days (the Loan panel shows the date). If the "
            "debt isn't paid by then the lender repossesses the Rogue and it's game "
            "over." + _reminders())


def _reminders():
    from core import debt
    days = [w for w in debt.WARN_AT if w < debt.loan_days()]
    if not days:
        return ""
    names = [str(d) for d in days]
    text = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]
    return f" The lender sends a reminder at {text} days left."


def _selling():
    from core.world import SELL_SPREAD
    pct = round((1 - SELL_SPREAD) * 100)
    return (f"A station pays {pct}% of the listed price when you sell to it, so two "
            "markets have to differ by more than that before hauling between "
            "them pays. Look for ▼ low in one place and ▲ high in another.")


def _price_days():
    from core import economy
    n = economy.PRICE_UPDATE_DAYS
    return (f"Markets only re-price every {n} days (the Trading Post shows the "
            "countdown), so a trade you've planned is still there when you "
            "arrive. The ↑↓ arrows compare with the previous update.")


def _contract_range():
    from core.missions import MAX_JUMPS
    return (f"■ contracts stay within {MAX_JUMPS[1]} jumps of the board, ■ ■ within "
            f"{MAX_JUMPS[2]}, and ■ ■ ■ can send you anywhere. Harder ones move more "
            "cargo for more pay, and pay also grows with the jumps to the "
            "destination and the cargo's value.")


def _pirates():
    from core import encounter
    arr = round(encounter.SYSTEM_ARRIVAL_CHANCE * 100)
    jump = round(encounter.JUMP_CHANCE * 100)
    return ("Space isn't safe. A pirate can jump you when you dock somewhere "
            f"(about {arr}% of the time) or when you arrive from a jump "
            f"(about {jump}%). Each turn you get three choices:")


def _upgrade_rows():
    from core import shipyard
    blurbs = {
        "cargo": ("Cargo Hold", "+10 cargo space each"),
        "fuel": ("Fuel Tank", "+50 fuel each"),
        "hull": ("Hull Plating", "+25 hull each"),
        "scanrange": ("Long-Range Scan", "range 2/3/4 jumps"),
        "jumprange": ("Star Jump Scan", "links 2/3/4 jumps out"),
    }
    rows = []
    for uid, name, offers in shipyard.UPGRADES:
        label, blurb = blurbs.get(uid, (name[:15], ""))
        prices = " / ".join(f"{price:,}" for price, _ in offers)
        rows.append(f"{label} | {blurb}: {prices} cr")
    return rows


# Each page: (title, [paragraphs]). A paragraph starting with "*" is a
# heading; "key | text" lines render as a key/description table row. A
# paragraph can also be a function returning text (or a list of lines), so
# numbers are always read from the game itself.
PAGES = [
    ("The basics", [
        "*Your goal",
        _goal,
        "*The screen",
        "The big window is the map. On the right: your Ship (credits, hull, "
        "fuel, cargo), the Loan, where you are, your Contracts, the comms "
        "log and the keys for the current screen.",
        "*Getting around: SPACE",
        "SPACE opens the quick menu from anywhere: every screen with its "
        "key, the station's facilities when docked, and every planet, station "
        "and gate in the system - pick one and the autopilot flies you there "
        "and docks (\"Nearest market\" lands you right in its Trading Post).",
        "*Galaxy seeds",
        "Every galaxy is built from a seed number, shown on the title screen: "
        "S types one and L replays your last galaxy. The same seed always gives "
        "the same galaxy. The tutorial runs in its own practice galaxy; your "
        "real game starts when it ends.",
        "*Tutorial: T",
        "T hides or brings back the tutorial card while you play. On the title "
        "screen it turns the tutorial on or off for the next run.",
    ]),
    ("Trading", [
        "*Buy low, sell high",
        "Dock at a planet or station and open the Trading Post. Each system "
        "makes some goods (cheap) and needs others (expensive).",
        "*Reading the market",
        "VS GALAXY compares the price with today's galaxy average. ▼ low "
        "means it's a good buy here; ▲ high means it's a good place to sell. "
        "Prices move as traders come and go; ↑↓ next to a price shows how it "
        "changed at the last update.",
        "*Cargo space",
        "Your hold starts at 20 units. Every good has a SIZE - Machinery takes 4 "
        "units, Luxury Goods only 1. Check the Cargo bar before you buy.",
        "*Selling",
        _selling,
        "*Prices hold for a few days",
        _price_days,
        "*Profit info",
        "The Trading Post shows what you paid on average, the profit per "
        "unit if you sold here, and the best sell and cheapest buy prices "
        "you've seen elsewhere (from the price log, K).",
        "↑↓ | choose a good",
        "→ or B | buy one",
        "← or S | sell one",
    ]),
    ("Contracts", [
        "*The Missions Board",
        "Stations post up to 4 delivery contracts a day - a fresh set each "
        "day, and one you've finished won't come back. Accepting one loads "
        "the cargo straight into your hold, so you need the free space.",
        "*Contract cargo",
        "Contract cargo is tagged with the system it came from and listed "
        "on its own rows in the cargo hold (I). It can't be sold, and goods "
        "you bought on a market don't count: only the cargo the contract "
        "gave you completes it.",
        "*Delivering",
        "Fly to the destination planet, dock, open its Missions Board and "
        "press ENTER on the contract (it shows DELIVER).",
        "*Keeping track",
        "Contracts show in the sidebar and in the Contract Log (P). On the "
        "board, V shows the destination on the galaxy chart.",
        "*Difficulty",
        _contract_range,
    ]),
    ("Travel", [
        "*Autopilot",
        "TAB flies you to the next planet, station or gate in the system "
        "(Shift+TAB: previous). Or scan (X), move the cursor and press ENTER "
        "to fly there. Any arrow key takes back control. Scanning a planet, "
        "station or gate also shows how many moves the trip takes.",
        "*Jump gates",
        "Each system has Θ jump gates to its neighbours. Fly onto one and "
        "press ENTER to see the route, the fuel it needs and the destination.",
        "*Fuel",
        "Flying inside a system is free; only jump gates burn fuel. Longer "
        "jumps need more, the jump menu shows how much, and a full tank lasts "
        "about a dozen jumps. Refuel when docked (5). If you can't reach any "
        "gate and can't buy fuel, you're stranded - game over.",
        "*The galaxy chart (M)",
        "Shows every system. Dotted lines are the jumps from where you are - "
        "1 jump out to start, and each Star Jump Scanner level (shipyard) "
        "shows one more jump of links; "
        "☼ marks contract destinations. Zoom in past x2 (or ENTER while "
        "scanning a star) to preview that system's planets, stations and gates. "
        "Inside scanner range the map is fully labelled; one jump beyond it, "
        "the map is visible but unlabelled, and farther systems show no data. "
        "If your scanner covers the system, the preview also shows the fuel "
        "for the gate route there.",
        "←↑↓→ | scroll (Shift = faster)",
        "+ / - / wheel | zoom in and out",
        "+ at x2 / ENTER | system preview (planets, gates)",
        "Z | cycle zoom levels",
        "C | centre on your ship",
        "X | scan: inspect a star",
        "TAB | hop the scanner to the next star",
        "N | show / hide the minimap",
        "R | show trade-route heat",
    ]),
    ("The loan", [
        "*The deadline",
        _loan_deadline,
        "*Time",
        "A day passes with every hyperspace jump (which also resets the "
        "50-move clock) and with every 50 moves inside a system - flying is "
        "free, but time still passes. The day counter is in the Ship panel.",
        "*Paying",
        "There are no instalments. At any station press 6 (Pay Debt), type "
        "any amount and press ENTER - M fills in the most you can pay.",
        "*Winning",
        "Pay the debt down to zero and the ship is yours. You can keep "
        "flying afterwards.",
        "*Other ways to lose",
        "You can also lose by being stranded (no fuel for any gate and "
        "nothing left to sell for fuel) or by being destroyed in combat.",
    ]),
    ("Ship and combat", [
        "*The shipyard",
        "Press 2 when docked. Upgrades are bought in order and kept for the "
        "whole run. The Long-Range Scan widens your market intelligence; the "
        "Star Jump Scan draws more jump links on the chart.",
        _upgrade_rows,
        "*Pirates",
        _pirates,
        "Attack | hit them; their defence reduces the damage",
        "Defend | double your defence until your next turn",
        "Escape | try to run - a faster engine helps",
        "*Afterwards",
        "Win and you salvage credits from the wreck. Lose and you're towed "
        "to a station and charged 2 credits for every point of hull damage - "
        "unless your hull hits zero, which ends the run.",
    ]),
    ("The exchange", [
        "*A living economy",
        "Dozens of NPC freighters fly the jump lanes every day, buying where "
        "goods are cheap and selling where they're dear. Every trade moves "
        "that market's price - and so do yours.",
        "*Market intelligence",
        "The Exchange is information only - buy and sell at station Trading "
        "Posts. It shows LIVE markets inside scanner range, STALE last-known "
        "records outside it, and UNKNOWN systems with no prices at all.",
        "*Long-Range System Scanner",
        "A standard scanner is fitted free and covers your system plus one "
        "jump. Shipyard upgrades extend it to 2, 3 and 4 jumps. Distances "
        "follow the real jump-gate network, never the chart's straight lines. "
        "The system map also shows one jump beyond scanner range, but without "
        "object labels. Fly on and the scan moves with you.",
        "*Cheap or dear?",
        "Each known buy price is compared with the known average. ▼ means it "
        "is at least 15% cheaper (a good place to buy); ▲ means it is at "
        "least 15% dearer (a good place to sell). STALE prices are historical, "
        "never current.",
        "*Trade routes",
        "The lanes freighters use most become trade routes. Busy routes mean "
        "big price swings at both ends. Press R on the galaxy chart to see "
        "them glow; the Exchange lists nearby lanes and the busiest elsewhere.",
        "*The market wire",
        "Pirates on a route, mining strikes, harvests and shortages all move "
        "prices. Watch the wire for trade tips.",
        "E | open the Galactic Exchange",
        "1-5 / ←→ | switch tab (Overview ... Routes)",
        "R | trade-route heat on the galaxy chart",
    ]),
    ("Keys and tools", [
        "←↑↓→ | fly / move cursor / choose",
        "ENTER | dock, confirm, accept, deliver",
        "ESC | back / cancel",
        "SPACE | quick menu: any screen or place",
        "TAB | autopilot target / next station screen",
        "1-6 | station: 1 Trade 2 Yard 3 Jobs 5 Fuel 6 Debt",
        "M / X | galaxy chart / scan mode",
        "I / L / P | cargo hold / comms log / contract log",
        "E / J / K / O | exchange / notebook / price log / radio",
        "H / T | this handbook / show or hide the tutorial",
        "F4 | mute / unmute music",
        "F5-F8 | music / sound effects volume",
        "F9 | classic / modern look",
        "F10 | change font",
        "F11 | fullscreen",
        "Q | save and go to the main menu",
        "*Notebook: J",
        "ENTER writes a note; docked at a market, R writes down all of its "
        "prices with the day. Notes are kept per galaxy seed and saved "
        "between runs.",
        "*Price log: K",
        "Every market price you've seen, with the cheapest and dearest for "
        "each good and the SPREAD (= profit per unit if you move it). It "
        "fills in by itself whenever you open a Trading Post; C clears it.",
        "*Radio: O",
        "Pick any track, skip with ←→, and TAB switches between shuffle, in "
        "order and repeat one. +/- volume, X switches the radio off and on. "
        "Drop more music into sfx/music and it becomes a new station.",
    ]),
]


TABS = ["Basics", "Trade", "Jobs", "Travel", "Loan", "Ship", "Exchange", "Keys"]


def _expand(paras):
    """Resolve function paragraphs into plain lines."""
    out = []
    for p in paras:
        if callable(p):
            p = p()
        out.extend(p if isinstance(p, list) else [p])
    return out


def draw(console, width, height=ui.MAP_H):
    H = min(46, ui.MAP_H - 2)        # fits shorter (mobile) screens
    page = max(0, min(state.help_page, len(PAGES) - 1))
    state.help_page = page
    title, paras = PAGES[page]
    paras = _expand(paras)
    x, y = ui.window(console, W, H, "Pilot's Handbook",
                     right_title=f"page {page + 1}/{len(PAGES)}")
    ix, iw = x + 3, W - 6

    # tab strip
    tx = ix
    for i, t in enumerate(TABS):
        label = f" {t} "
        if tx + len(label) > x + W - 3:
            break
        on = i == page
        ui.text(console, tx, y + 2, label, fg=(0, 0, 0) if on else ui.DIM,
                bg=ui.ACCENT if on else None)
        tx += len(label) + 1
    ui.hline(console, x, y + 3, W, fg=ui.BORDER_HI)

    ui.text(console, ix, y + 4, title.upper(), fg=ui.KEY)
    cy = y + 6
    for p in paras:
        if cy >= y + H - 3:
            break
        if p.startswith("*"):
            if cy > y + 6:
                cy += 1
            ui.text(console, ix, cy, p[1:].upper(), fg=ui.TITLE)
            cy += 1
        elif " | " in p:
            key, desc = p.split(" | ", 1)
            ui.text(console, ix + 1, cy, key, fg=ui.KEY)
            ui.text(console, ix + 17, cy, ui.clip(desc, iw - 17), fg=ui.TEXT)
            cy += 1
        else:
            cy += ui.paragraph(console, ix, cy, iw, p, fg=ui.TEXT)

    ui.hint_row_centered(console, x + W // 2, y + H - 2,
                         [("←→", "Page"), ("H", "Close"), ("ESC", "Close")])
