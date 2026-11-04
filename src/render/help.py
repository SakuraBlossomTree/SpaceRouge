"""Render the HELP overlay: the Pilot's Handbook (paged reference)."""

from core import state
from render import ui

W, H = 72, 46

# Each page: (title, [paragraphs]). A paragraph starting with "*" is a
# heading; "key | text" lines render as a key/description table row.
PAGES = [
    ("The basics", [
        "*Your goal",
        "You fly the Rogue, a light hauler bought on a 250,000 credit loan. "
        "Trade, run contracts and pay the loan off before it ruins you.",
        "*The screen",
        "The big window is the map. On the right: your Ship (credits, hull, "
        "fuel, cargo), the Loan, where you are, your Contracts, the comms "
        "log and the keys for the current screen.",
        "*Getting around: SPACE",
        "SPACE opens the quick menu from anywhere: every screen with its "
        "key, the station's facilities when docked, and every planet, station "
        "and gate in the system - pick one and the autopilot flies you there "
        "and docks (\"Nearest market\" lands you right in its Trading Post).",
        "*Notebook: J",
        "J opens your notebook. ENTER writes a note; docked at a market, R "
        "writes down all of its prices with the day. Notes are kept per galaxy "
        "seed and saved between runs.",
        "*Price log: K",
        "K shows the Price log: every market price you've seen, with the "
        "cheapest and dearest for each good and the SPREAD (= profit per "
        "unit if you move it). It fills up by itself every time you open a "
        "Trading Post; C clears it. The notebook (J) is for everything else.",
        "*Radio: O",
        "O opens the ship's radio: pick any track, skip with ←→, and TAB "
        "switches between shuffle, in order and repeat one. +/- volume, X "
        "switches the radio off and on. Drop more music into sfx/music and "
        "it shows up as a new station.",
        "*Time",
        "Each hyperspace jump takes one day. On Hard, every 50 moves inside a "
        "system is a day too.",
        "*Fuel",
        "Easy (pick on the title screen): flying inside a system is free and "
        "only jump gates use fuel - longer jumps need more, the jump menu shows "
        "how much, and a full tank lasts about a dozen jumps. If you can't "
        "reach any gate and can't buy fuel, you're stranded.",
        "Hard: every move burns about 1 fuel - more with a heavy hold, a "
        "damaged hull or in dense systems - and 50 moves make a day. Run dry "
        "and you drift into the void. Jumps need no fuel.",
        "Either way, refuel when docked (5)."
    ]),
    ("Trading", [
        "*Buy low, sell high",
        "Dock at a planet or station and open the Trading Post. Each system "
        "makes some goods (cheap) and needs others (expensive).",
        "*Reading the market",
        "VS GALAXY compares the price with today's galaxy average. ▼ low "
        "means it's a good buy here; ▲ high means it's a good place to sell. "
        "Prices change every day as traders come and go; ↑↓ next to a price "
        "shows how it moved since yesterday.",
        "*Cargo space",
        "Your hold has 20 units. Every good has a SIZE - Machinery takes 4 "
        "units, Luxury Goods only 1. Check the Cargo bar before you buy.",
        "↑↓ | choose a good",
        "→ or B | buy one",
        "← or S | sell one",
    ]),
    ("Contracts", [
        "*The Missions Board",
        "Stations post delivery contracts. Accepting one loads the cargo "
        "straight into your hold, so you need the free space.",
        "*Delivering",
        "Fly to the destination planet, dock, open its Missions Board and "
        "press ENTER on the contract (it shows DELIVER). Don't sell the "
        "cargo on the way!",
        "*Keeping track",
        "Contracts show in the sidebar and in the Contract Log (P). On the "
        "board, V shows the destination on the galaxy chart.",
        "*Difficulty",
        "■ to ■ ■ ■: harder contracts move more cargo, further, for more pay.",
    ]),
    ("Travel", [
        "*Autopilot",
        "TAB flies you to the next planet, station or gate in the system "
        "(Shift+TAB: previous). Or scan (X), move the cursor and press ENTER "
        "to fly there. Any arrow key takes back control.",
        "*Jump gates",
        "Each system has Θ jump gates to its neighbours. Fly onto one and "
        "press ENTER to see the route, the toll and the destination.",
        "*The galaxy chart (M)",
        "Shows every system. Dotted lines are the jumps from where you are; "
        "☼ marks contract destinations. Zoom in past x2 (or ENTER while "
        "scanning a star) to preview that system's planets, stations and gates.",
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
        "*Instalments",
        "Every 7 days (the first is due on day 14) the instalment is taken "
        "from your credits automatically. The Loan panel shows when.",
        "*Missing a payment",
        "If you can't pay, it counts as a strike: 2% interest is added to "
        "the debt and the instalment grows. The warnings escalate - debt "
        "collectors, then bounty hunters.",
        "*Four strikes",
        "Miss four payments in a row and it's game over. Paying on time "
        "clears your strikes.",
        "*Winning",
        "Pay the debt down to zero and the ship is yours.",
    ]),
    ("Combat", [
        "*Pirates",
        "Space isn't safe. When a pirate attacks you get three choices each "
        "turn:",
        "Attack | hit them; their defence reduces the damage",
        "Defend | double your defence until your next turn",
        "Escape | try to run - a faster engine helps",
        "*Afterwards",
        "Win and you salvage credits from the wreck. Lose and you're towed "
        "to a station and charged for repairs - unless your hull hits zero.",
    ]),
    ("The exchange", [
        "*A living economy",
        "Dozens of NPC freighters fly the jump lanes every day, buying where "
        "goods are cheap and selling where they're dear. Every trade moves "
        "that market's price - and so do yours.",
        "*Long-range scanner",
        "The Exchange needs a long-range market scanner to compare systems. "
        "Your ship does not start with one: without it you only see prices "
        "at the market you are docked at.",
        "*Local market scan",
        "With a scanner fitted, the Exchange reports markets within 1 jump "
        "of your current system. Fly on and the scan moves with you.",
        "*Cheap or dear?",
        "Each good is compared with the regional average. ▼ means it is at "
        "least 15% cheaper here (a good place to buy); ▲ means it is at "
        "least 15% dearer (a good place to sell).",
        "*Trade routes",
        "The lanes freighters use most become trade routes. Busy routes mean "
        "big price swings at both ends. Press R on the galaxy chart to see "
        "them glow; the Exchange lists nearby lanes and the busiest elsewhere.",
        "*The market wire",
        "Pirates on a route, mining strikes, harvests and shortages all move "
        "prices. Watch the wire for trade tips.",
        "E | open the Galactic Exchange",
        "1-4 / ←→ | Overview, Markets, Goods, Routes",
        "R | trade-route heat on the galaxy chart",
    ]),
    ("All controls", [
        "←↑↓→ | fly / move cursor / choose",
        "ENTER | dock, confirm, accept, deliver",
        "ESC | back / cancel",
        "1-5 | station menu shortcuts",
        "M | galaxy chart",
        "X | scan mode",
        "I | cargo hold",
        "L | comms log",
        "P | contract log",
        "E | galactic exchange",
        "H | this handbook",
        "T | show / hide the tutorial",
        "F10 | change font",
        "F4 | mute / unmute music",
        "F5 / F6 | music volume down / up",
        "F7 / F8 | sound effects volume down / up",
        "F11 | fullscreen",
        "Q | quit",
    ]),
]


TABS = ["Basics", "Trade", "Jobs", "Travel", "Loan", "Combat", "Exchange", "Keys"]


def draw(console, width, height=ui.MAP_H):
    H = min(46, ui.MAP_H - 2)        # fits shorter (mobile) screens
    page = max(0, min(state.help_page, len(PAGES) - 1))
    state.help_page = page
    title, paras = PAGES[page]
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
