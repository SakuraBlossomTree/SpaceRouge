"""The living economy: NPC trade fleets, live prices, companies and stocks.

How it fits together (one tick = one game day):

  markets      Every planet/station market has a supply level per good.
               Price = equilibrium price * (100 / supply) ** 0.6, so buying
               (less supply) pushes the price up and selling pushes it down.
               Supply drifts back toward its target every day.

  traders      NPC ships owned by companies. Each looks up to 3 jumps ahead
               for the best profit-per-day trade, buys, flies one jump per
               day, sells, and repeats. Their buying and selling is what
               moves market prices, and every jump they make adds traffic
               to that route.

  routes       Traffic per jump link over the last 7 days = the trade routes.

  companies    Each corporation (one per faction) owns a shipping line plus
               producers tied to the goods its home systems make. Revenue:
               shipping = profit of its fleet; producers = value of their
               goods leaving their home systems + their own fleet's profit.
               Share prices drift toward revenue-based fair value, plus
               market mood, corporate mood, noise and news.

  news         Random events (pirates on a busy route, mining strikes,
               harvests, shortages, scandals, contracts) change supply
               targets, trader behaviour and share prices.

Nothing here draws anything; render/exchange.py shows it.
"""

import math
import random
from collections import defaultdict, deque, namedtuple

from core import state
from core.world import COMMODITIES, BASE_PRICES, FACTIONS

# --- Tuning -------------------------------------------------------------------

S0 = 100.0            # normal supply level
ELASTICITY = 0.6      # how hard supply moves price
REGEN = 0.12          # share of the gap to target recovered per day
IMPACT = 0.45         # supply removed per unit bought (added per unit sold)
MIN_SUPPLY = 12.0
PRICE_CLAMP = (0.45, 2.6)

PLAN_DEPTH = 3        # jumps an NPC trader looks ahead


def scan_depth():
    """Current Long-Range System Scanner radius in jumps."""
    from core import scanner
    return scanner.radius()
PRICE_BAND = 0.15     # ±15% vs the regional average counts as cheap/dear
HISTORY = 120         # days of history kept for charts
ROUTE_WINDOW = 7      # days of traffic that make a "trade route"
WARMUP_DAYS = 60      # simulated before day 1 so charts have history
CALIBRATE_DAY = -45   # stocks start trading here (earlier days just settle prices)
EVENT_CHANCE = 0.28   # chance of a news event per day

# One profitable nearby trade: buy at buy_market, sell at sell_market.
Trade = namedtuple(
    "Trade",
    "good buy_price buy_market buy_system buy_jumps "
    "sell_price sell_market sell_system sell_jumps hops profit",
)


def price_band(price, reference):
    """-1 = cheap, 0 = fair, 1 = dear compared with a reference price."""
    if not reference:
        return 0
    if price <= reference * (1 - PRICE_BAND):
        return -1
    if price >= reference * (1 + PRICE_BAND):
        return 1
    return 0

SECTORS = {
    "Shipping":      [],
    "Agriculture":   ["Food", "Water"],
    "Mining":        ["Ore", "Rare Minerals"],
    "Manufacturing": ["Machinery", "Electronics"],
    "Biotech":       ["Medicine", "Electronics"],
    "Luxury":        ["Luxury Goods"],
}

NAME_PARTS = {
    "Shipping":      (["Starlane", "Driftway", "Longhaul", "Meridian", "Corsair",
                       "Vector", "Farpoint", "Halcyon"], ["Freight", "Logistics", "Lines", "Haulage"]),
    "Agriculture":   (["Greenbelt", "Harvest", "Verdant", "Hydra", "Sunfield", "Terra"],
                      ["Agro", "Farms", "Foods", "Growers"]),
    "Mining":        (["Deepcore", "Ironvein", "Regolith", "Basalt", "Cobalt", "Quarry"],
                      ["Mining", "Extraction", "Minerals", "Ores"]),
    "Manufacturing": (["Forge", "Titan", "Helix", "Atlas", "Anvil", "Kestrel"],
                      ["Industries", "Works", "Fabrication", "Heavy"]),
    "Biotech":       (["Quantum", "Neuro", "Photon", "Lumen", "Vita", "Cortex"],
                      ["Systems", "Dynamics", "Labs", "Biotech"]),
    "Luxury":        (["Aurora", "Velvet", "Opal", "Gilded", "Sable", "Orchid"],
                      ["Imports", "Luxuries", "House", "Collective"]),
}

SHIP_ADJ = ["Iron", "Silent", "Red", "Lucky", "Distant", "Gray", "Swift", "Old",
            "Bright", "Wandering", "Heavy", "Last", "Golden", "Cold", "Patient"]
SHIP_NOUN = ["Gull", "Mule", "Comet", "Barge", "Heron", "Promise", "Lantern",
             "Drifter", "Ox", "Sparrow", "Fortune", "Anchor", "Pilgrim", "Kite"]

CORP_TICKERS = {
    "United Nations": "UNX", "Independent": "IND", "Free Traders Guild": "FTG",
    "Outer Colonies": "OCC", "Corporate Syndicate": "CSY", "Frontier Alliance": "FAL",
}


# --- Data classes --------------------------------------------------------------

class MarketState:
    """Live supply/demand for one market dict (shared dicts = one market)."""

    def __init__(self, market, system, locations):
        self.market = market                 # the dict the rest of the game reads
        self.system = system                 # system name
        self.locations = locations           # location names using this market
        self.id = None                       # stable market id, set by Economy
        self.eq = dict(market)               # equilibrium prices
        self.supply = {c: S0 for c in market}
        self.target = {c: S0 for c in market}
        self.prev = dict(market)             # yesterday's prices
        self.exports = defaultdict(float)    # units bought by traders today

    @property
    def name(self):
        return self.locations[0] if self.locations else self.system

    def reprice(self, good=None):
        goods = [good] if good else list(self.market)
        lo, hi = PRICE_CLAMP
        for c in goods:
            eq = self.eq[c]
            raw = eq * (S0 / max(MIN_SUPPLY, self.supply[c])) ** ELASTICITY
            self.market[c] = max(1, int(round(min(eq * hi, max(eq * lo, raw)))))

    def trade(self, good, units):
        """units > 0: bought from this market; < 0: sold to it."""
        if good not in self.supply:
            return
        self.supply[good] = max(MIN_SUPPLY, self.supply[good] - units * IMPACT)
        self.reprice(good)


class Corporation:
    def __init__(self, name, ticker):
        self.name = name
        self.ticker = ticker
        self.companies = []
        self.history = []          # index values
        self.mood = 0.0            # today's corporate shock (log return)

    @property
    def index(self):
        return self.history[-1] if self.history else 100.0


class Company:
    def __init__(self, name, ticker, corp, sector, goods, homes, price):
        self.name = name
        self.ticker = ticker
        self.corp = corp
        self.sector = sector
        self.goods = goods
        self.homes = homes         # system names it produces in
        self.price = price
        self.history = [price]
        self.fleet = []
        self.rev_today = 0.0
        self.rev_hist = []
        self.ema = None
        self.ref = None            # revenue level that matches the starting price
        self.ref_price = price
        self.shock = 0.0           # news shock applied on the next tick

    def change(self, days):
        if len(self.history) <= days:
            return 0.0
        old = self.history[-1 - days]
        return (self.history[-1] - old) / old if old else 0.0


class Trader:
    def __init__(self, name, company, system, capacity):
        self.name = name
        self.company = company
        self.system = system
        self.capacity = capacity
        self.path = deque()
        self.cargo = None          # (good, qty, unit_cost, dest MarketState)
        self.idle_days = 0


# --- Economy ---------------------------------------------------------------------

class Economy:
    def __init__(self, stars, seed=None):
        self.rng = random.Random(seed)
        self.day = -WARMUP_DAYS
        self.stars = {s.name: s for s in stars}
        self.adj = {s.name: sorted({jp.destination for jp in s.system.jump_points
                                    if jp.destination in self.stars}) for s in stars}
        self._bfs_cache = {}

        # markets (planet + station sharing a dict count as one market)
        self.markets = []
        self.markets_in = defaultdict(list)
        by_id = {}
        for s in stars:
            for loc in [*s.system.planets, *s.system.stations]:
                if not loc.market:
                    continue
                key = id(loc.market)
                if key in by_id:
                    by_id[key].locations.append(loc.name)
                    continue
                ms = MarketState(loc.market, s.name, [loc.name])
                # Stable within a galaxy seed: markets are created in a
                # deterministic order (planets, then stations) per system.
                ms.id = f"{s.name}:{len(self.markets_in[s.name])}"
                by_id[key] = ms
                self.markets.append(ms)
                self.markets_in[s.name].append(ms)
        self._by_dict = by_id

        self.traffic = defaultdict(lambda: deque([0.0] * ROUTE_WINDOW, maxlen=ROUTE_WINDOW))
        self.route_goods = defaultdict(lambda: defaultdict(float))
        self.traffic_today = defaultdict(float)
        self.losses_today = 0
        self.effects = []          # active news effects
        self.news = []             # (day, text, kind)
        self.trade_news = []       # market-relevant subset for the Exchange
        self.composite = []        # composite index history
        self.avg_history = {c: [] for c in COMMODITIES}
        self.pending = defaultdict(float)  # cargo already headed to (market, good)

        self._build_corporations(stars)
        self._build_fleets()
        self.calibrated = False

    # ---- setup --------------------------------------------------------------

    def _build_corporations(self, stars):
        rng = self.rng
        homes = defaultdict(set)
        for s in stars:
            for loc in [*s.system.planets, *s.system.stations]:
                owner = getattr(loc, "govement", None) or getattr(loc, "faction", None)
                if owner in FACTIONS:
                    homes[owner].add(s.name)

        self.corporations = []
        self.companies = []
        used_names, used_tickers = set(), set()
        taken = set()
        for faction in FACTIONS:
            corp = Corporation(faction, CORP_TICKERS.get(faction, faction[:3].upper()))
            self.corporations.append(corp)
            corp_homes = sorted(homes.get(faction) or rng.sample(sorted(self.stars), 3))

            # which goods do this corp's home markets export cheaply?
            cheap = defaultdict(int)
            for sname in corp_homes:
                for ms in self.markets_in[sname]:
                    for c, p in ms.eq.items():
                        if p < BASE_PRICES[c] * 0.8:
                            cheap[c] += 1
            sector_score = {sec: sum(cheap[g] for g in goods)
                            for sec, goods in SECTORS.items() if goods}
            ranked = sorted(sector_score, key=lambda k: (-sector_score[k], rng.random()))
            # first producer: what its home systems are best at; second: a
            # sector no corporation has yet, so the market covers every industry
            first = ranked[0]
            fresh = [sec for sec in ranked if sec != first and sec not in taken]
            second = fresh[0] if fresh else ranked[1]
            producers = [first, second]
            taken.update(producers)

            for sector in ["Shipping"] + producers:
                prefixes, suffixes = NAME_PARTS[sector]
                for _ in range(50):
                    name = f"{rng.choice(prefixes)} {rng.choice(suffixes)}"
                    if name not in used_names:
                        break
                used_names.add(name)
                ticker = self._ticker(name, used_tickers)
                goods = SECTORS[sector]
                comp_homes = [h for h in corp_homes
                              if any(g in ms.eq for ms in self.markets_in[h] for g in goods)] or corp_homes
                price = round(rng.uniform(18, 140), 2)
                company = Company(name, ticker, corp, sector, goods, comp_homes[:6], price)
                corp.companies.append(company)
                self.companies.append(company)

    @staticmethod
    def _ticker(name, used):
        """'Farpoint Lines' -> 'FARL' (unique; falls back to a digit)."""
        words = name.upper().split()
        base = (words[0][:3] + (words[1][0] if len(words) > 1 else words[0][3:4]))[:4]
        t, n = base, 1
        while t in used:
            t = base[:3] + str(n)
            n += 1
        used.add(t)
        return t

    def _build_fleets(self):
        rng = self.rng
        self.traders = []
        used = set()
        for company in self.companies:
            n = rng.randint(5, 7) if company.sector == "Shipping" else rng.randint(1, 2)
            for _ in range(n):
                for _ in range(50):
                    name = f"{rng.choice(SHIP_ADJ)} {rng.choice(SHIP_NOUN)}"
                    if name not in used:
                        break
                used.add(name)
                start = rng.choice(company.homes) if company.homes else rng.choice(sorted(self.stars))
                t = Trader(name, company, start, rng.randint(18, 45))
                company.fleet.append(t)
                self.traders.append(t)

    # ---- helpers ------------------------------------------------------------

    def market_for(self, location):
        if location is None or not location.market:
            return None
        return self._by_dict.get(id(location.market))

    def _bfs(self, start, depth=PLAN_DEPTH):
        key = (start, depth)
        if key not in self._bfs_cache:
            dist, parent = {start: 0}, {start: None}
            q = deque([start])
            while q:
                n = q.popleft()
                if dist[n] >= depth:
                    continue
                for m in self.adj.get(n, ()):
                    if m not in dist:
                        dist[m] = dist[n] + 1
                        parent[m] = n
                        q.append(m)
            self._bfs_cache[key] = (dist, parent)
        return self._bfs_cache[key]

    @staticmethod
    def _path(parent, dest):
        path = []
        while parent[dest] is not None:
            path.append(dest)
            dest = parent[dest]
        return list(reversed(path))

    def systems_within(self, start, depth=None):
        """{system: jumps} for the start system and everything nearby."""
        depth = scan_depth() if depth is None else depth
        if not start or start not in self.stars:
            return {}
        return dict(self._bfs(start, depth)[0])

    def nearby_markets(self, start, depth=None):
        """[(jumps, system, MarketState)] visible from the start system."""
        rows = []
        for sname, jumps in self.systems_within(start, depth).items():
            for ms in self.markets_in.get(sname, ()):
                rows.append((jumps, sname, ms))
        rows.sort(key=lambda row: (row[0], row[1], row[2].name))
        return rows

    def system_prices(self, system):
        """good -> [(price, MarketState)] for every market in one system."""
        rows = defaultdict(list)
        for ms in self.markets_in.get(system, ()):
            for good, price in ms.market.items():
                rows[good].append((price, ms))
        for quotes in rows.values():
            quotes.sort(key=lambda quote: quote[0])
        return dict(rows)

    def regional_prices(self, start, depth=None):
        """good -> average price across every market within scan range."""
        prices = defaultdict(list)
        for _, _, ms in self.nearby_markets(start, depth):
            for good, price in ms.market.items():
                prices[good].append(price)
        return {good: sum(v) / len(v) for good, v in prices.items() if v}

    def nearby_trades(self, start, depth=None):
        """One best buy-low / sell-high trade per good, ranked by profit/jump.

        Only markets inside the scan range are considered. The result is
        what the Galactic Exchange shows, so remote prices stay hidden.
        """
        depth = scan_depth() if depth is None else depth
        markets = self.nearby_markets(start, depth)
        if not markets:
            return []

        systems = sorted({sname for _, sname, _ in markets})
        reach = max(depth * 2 + 1, PLAN_DEPTH)
        distances = {sname: self._bfs(sname, reach)[0] for sname in systems}

        best = {}
        for good in COMMODITIES:
            # Buying cheapest and selling dearest is always the best pair,
            # so each system only needs its two extreme markets.
            per_system = {}
            for jumps, sname, ms in markets:
                price = ms.market.get(good)
                if price is None:
                    continue
                rec = per_system.get(sname)
                if rec is None:
                    per_system[sname] = [price, price, ms, ms, jumps]
                else:
                    if price < rec[0]:
                        rec[0], rec[2] = price, ms
                    if price > rec[1]:
                        rec[1], rec[3] = price, ms

            for bsys, (bp, _, bms, _, bj) in per_system.items():
                for ssys, (_, sp, _, sms, sj) in per_system.items():
                    if bsys == ssys:
                        continue
                    hops = distances[bsys].get(ssys)
                    if hops is None:
                        continue
                    profit = sp - bp
                    if profit <= 0:
                        continue
                    score = profit / (hops + 1)
                    old = best.get(good)
                    old_score = old.profit / (old.hops + 1) if old else -1
                    if score > old_score or (score == old_score and
                                             (old is None or profit > old.profit)):
                        best[good] = Trade(
                            good, bp, bms, bsys, bj,
                            sp, sms, ssys, sj, hops, profit,
                        )

        return sorted(best.values(),
                      key=lambda t: (t.profit / (t.hops + 1), t.profit),
                      reverse=True)

    def _pirate_edges(self):
        return {frozenset(e["edge"]) for e in self.effects if e["kind"] == "pirates"}

    def avg_price(self, good):
        prices = [ms.market[good] for ms in self.markets if good in ms.market]
        return sum(prices) / len(prices) if prices else BASE_PRICES.get(good, 1)

    def price_extremes(self, good):
        rows = [(ms.market[good], ms) for ms in self.markets if good in ms.market]
        if not rows:
            return None, None
        return min(rows, key=lambda r: r[0]), max(rows, key=lambda r: r[0])

    def top_routes(self, n=15):
        rows = []
        for edge, window in self.traffic.items():
            vol = sum(window)
            if vol <= 0:
                continue
            goods = self.route_goods[edge]
            main = max(goods, key=goods.get) if goods else "-"
            rows.append((vol, tuple(sorted(edge)), main))
        rows.sort(reverse=True)
        return rows[:n]

    def ships_on(self, edge):
        a, b = edge
        return sum(1 for t in self.traders
                   if (t.system == a and t.path and t.path[0] == b)
                   or (t.system == b and t.path and t.path[0] == a))

    def add_news(self, text, kind, trade=True):
        entry = (self.day, text, kind)
        self.news.append(entry)
        self.news = self.news[-60:]
        if trade:
            self.trade_news.append(entry)
            self.trade_news = self.trade_news[-40:]
        if self.calibrated:
            state.add_message(f"NEWS: {text}")

    # ---- trader brain -----------------------------------------------------------

    def _plan(self, t):
        here = self.markets_in.get(t.system, [])
        dist, parent = self._bfs(t.system)
        pirate = self._pirate_edges()

        sells = defaultdict(list)     # good -> [(effective price, system, jumps, market)]
        for sname, d in dist.items():
            for ms in self.markets_in.get(sname, ()):
                for c, p in ms.market.items():
                    # cargo already heading there will push the price down
                    crowd = self.pending[(id(ms), c)] * p * 0.006
                    sells[c].append((p - crowd, sname, d, ms))

        candidates = []
        for ms in here:
            for c, pb in ms.market.items():
                for eff, sname, d, mt in sells.get(c, ()):
                    if mt is ms or eff <= pb:
                        continue
                    gain = (eff - pb) * t.capacity / (d + 1)
                    candidates.append((gain, c, pb, ms, mt, sname))
        candidates.sort(key=lambda r: -r[0])
        candidates = candidates[:6]

        scored = []
        for gain, c, pb, ms, mt, sname in candidates:
            path = self._path(parent, sname)
            hops = zip([t.system] + path[:-1], path)
            if any(frozenset(h) in pirate for h in hops):
                gain *= 0.3
            scored.append((gain, c, pb, ms, mt, path))
        scored = [s for s in scored if s[0] > 8]

        if scored:
            # mostly the best deal, sometimes a runner-up: spreads traffic out
            weights = [s[0] ** 2 for s in scored]
            gain, c, pb, ms, mt, path = self.rng.choices(scored, weights=weights)[0]
            qty = t.capacity
            ms.trade(c, qty)
            ms.exports[c] += qty
            t.cargo = (c, qty, pb, mt)
            t.path = deque(path)
            self.pending[(id(mt), c)] += qty
            t.idle_days = 0
        else:
            # nothing worth hauling here: reposition to a random neighbour
            t.idle_days += 1
            nbrs = self.adj.get(t.system)
            if nbrs:
                t.path = deque([self.rng.choice(nbrs)])

    def _sell(self, t):
        c, qty, cost, mt = t.cargo
        price = mt.market.get(c, cost)
        mt.trade(c, -qty)
        self.pending[(id(mt), c)] = max(0.0, self.pending[(id(mt), c)] - qty)
        t.company.rev_today += (price - cost) * qty
        t.cargo = None

    def _move_traders(self):
        pirate = self._pirate_edges()
        for t in self.traders:
            if t.path:
                nxt = t.path.popleft()
                edge = frozenset((t.system, nxt))
                if t.cargo:
                    c, qty, cost, mt = t.cargo
                    self.traffic_today[edge] += qty
                    self.route_goods[edge][c] += qty
                    if edge in pirate and self.rng.random() < 0.3:
                        # raided: cargo lost
                        t.company.rev_today -= cost * qty
                        self.pending[(id(mt), c)] = max(0.0, self.pending[(id(mt), c)] - qty)
                        t.cargo = None
                        t.path.clear()
                        self.losses_today += 1
                else:
                    self.traffic_today[edge] += 2   # empty hulls still count a little
                t.system = nxt
            if not t.path:
                if t.cargo and t.cargo[3].system == t.system:
                    self._sell(t)
                if t.cargo is None:
                    self._plan(t)

    # ---- news events --------------------------------------------------------------

    def _maybe_event(self):
        if self.rng.random() > EVENT_CHANCE:
            return
        rng = self.rng
        kind = rng.choices(
            ["pirates", "strike", "harvest", "shortage", "scandal", "contract"],
            weights=[2, 2, 2, 2, 1, 2])[0]
        end = self.day + rng.randint(5, 11)

        if kind == "pirates":
            routes = self.top_routes(10)
            if not routes:
                return
            _, edge, _ = rng.choice(routes)
            self.effects.append({"kind": kind, "edge": edge, "end": end})
            for c in self.companies:
                if c.sector == "Shipping":
                    c.shock -= 0.03
            self.add_news(f"Pirates raiding the {edge[0]} - {edge[1]} route", "bad")
            return

        if kind in ("strike", "harvest", "shortage"):
            goods = {"strike": ["Ore", "Rare Minerals"], "harvest": ["Food", "Water"],
                     "shortage": ["Machinery", "Electronics", "Medicine"]}[kind]
            factor = {"strike": 0.45, "harvest": 1.8, "shortage": 0.5}[kind]
            pool = [ms for ms in self.markets if any(g in ms.market for g in goods)]
            if kind != "shortage":
                pool = [ms for ms in pool
                        if any(ms.eq.get(g, 1e9) < BASE_PRICES[g] * 0.8 for g in goods)] or pool
            if not pool:
                return
            ms = rng.choice(pool)
            self.effects.append({"kind": kind, "market": ms, "goods": goods,
                                 "factor": factor, "end": end})
            for comp in self.companies:
                if any(g in comp.goods for g in goods):
                    local = ms.system in comp.homes
                    if kind == "strike":
                        comp.shock += -0.07 if local else 0.02
                    elif kind == "harvest":
                        comp.shock += 0.03 if local else -0.01
                    else:
                        comp.shock += 0.04
            text = {"strike": f"Miners strike at {ms.name} ({ms.system}) - ore output collapses",
                    "harvest": f"Bumper harvest at {ms.name} ({ms.system}) floods food markets",
                    "shortage": f"Shortage of machinery and medicine at {ms.name} ({ms.system})"}[kind]
            self.add_news(text, "bad" if kind == "strike" else "info")
            return

        if kind == "scandal":
            corp = rng.choice(self.corporations)
            corp.mood -= 0.08
            self.add_news(f"Audit finds irregularities at {corp.name}", "bad", trade=False)
            return

        if kind == "contract":
            comp = rng.choice(self.companies)
            comp.shock += 0.07
            self.add_news(f"{comp.name} ({comp.ticker}) wins a major supply contract",
                          "good", trade=False)

    def _apply_effects(self):
        self.effects = [e for e in self.effects if e["end"] > self.day]
        for ms in self.markets:
            for c in ms.target:
                ms.target[c] = S0
        for e in self.effects:
            if "market" in e:
                for g in e["goods"]:
                    if g in e["market"].target:
                        e["market"].target[g] = S0 * e["factor"]

    # ---- stocks ---------------------------------------------------------------------

    def _update_companies(self):
        rng = self.rng
        mkt = rng.gauss(0.0004, 0.006)
        for corp in self.corporations:
            corp.mood += rng.gauss(0, 0.007)

        for comp in self.companies:
            if comp.sector != "Shipping":
                for h in comp.homes:
                    for ms in self.markets_in.get(h, ()):
                        for g in comp.goods:
                            comp.rev_today += ms.exports.get(g, 0) * ms.market.get(g, 0)
            comp.rev_hist.append(comp.rev_today)
            comp.rev_hist = comp.rev_hist[-HISTORY:]
            comp.ema = comp.rev_today if comp.ema is None else comp.ema * 0.85 + comp.rev_today * 0.15

            if self.calibrated:
                ratio = max(0.3, min(3.0, comp.ema / comp.ref)) if comp.ref else 1.0
                fair = comp.ref_price * ratio
                r = 0.08 * math.log(fair / comp.price) + mkt + comp.corp.mood + comp.shock
                r += rng.gauss(0, 0.018)
                comp.price = max(0.5, comp.price * math.exp(r))
            comp.history.append(round(comp.price, 2))
            comp.history = comp.history[-HISTORY:]
            comp.shock = 0.0
            comp.rev_today = 0.0

        for corp in self.corporations:
            vals = [c.price / c.history[0] for c in corp.companies if c.history and c.history[0]]
            corp.history.append(100.0 * sum(vals) / len(vals) if vals else 100.0)
            corp.history = corp.history[-HISTORY:]
            corp.mood = 0.0
        self.composite.append(sum(c.index for c in self.corporations) / len(self.corporations))
        self.composite = self.composite[-HISTORY:]

    def _calibrate(self):
        """After warm-up, tie each company's current price to its revenue level."""
        for comp in self.companies:
            recent = comp.rev_hist[-20:]
            mean = sum(recent) / len(recent) if recent else 0
            comp.ref = max(abs(mean), 50.0)
            comp.ema = max(comp.ema or 0, comp.ref * 0.5)
            comp.ref_price = comp.price
            comp.history = [comp.price]
        for corp in self.corporations:
            corp.history = [100.0]
        self.composite = [100.0]
        self.calibrated = True

    # ---- the daily tick -----------------------------------------------------------------

    def tick(self):
        self.day += 1
        for ms in self.markets:
            ms.prev = dict(ms.market)
            ms.exports.clear()
        self._maybe_event()
        self._apply_effects()
        for ms in self.markets:
            for c in ms.supply:
                ms.supply[c] += (ms.target[c] - ms.supply[c]) * REGEN
            ms.reprice()

        self.traffic_today.clear()
        self.losses_today = 0
        self._move_traders()
        for edge in set(self.traffic) | set(self.traffic_today):
            self.traffic[edge].append(self.traffic_today.get(edge, 0.0))
        # fade the route-goods mix so it reflects recent traffic
        for goods in self.route_goods.values():
            for g in goods:
                goods[g] *= 0.85

        self._update_companies()
        for c in COMMODITIES:
            self.avg_history[c].append(self.avg_price(c))
            self.avg_history[c] = self.avg_history[c][-HISTORY:]

        if self.day == CALIBRATE_DAY and not self.calibrated:
            self._calibrate()

    def warmup(self):
        while self.day < 0:
            self.tick()

    # ---- player hooks ---------------------------------------------------------------------

    def player_trade(self, location, good, units):
        ms = self.market_for(location)
        if ms:
            ms.trade(good, units)


def init(stars, seed=None):
    """Build the economy for a new galaxy and simulate the warm-up period."""
    state.economy = Economy(stars, seed)
    state.economy.warmup()
    return state.economy


PRICE_UPDATE_DAYS = 5   # markets re-price every this many days, so a trade stays readable


def days_to_update():
    """Days until the markets next change their prices."""
    return PRICE_UPDATE_DAYS - state.day % PRICE_UPDATE_DAYS


def tick(days=1):
    """Run `days` days of economy in one go. The arrows next to prices compare
    with the prices from before the whole batch."""
    ec = getattr(state, "economy", None)
    if ec is None:
        return
    before = [(ms, dict(ms.market)) for ms in ec.markets]
    for _ in range(days):
        ec.tick()
    if days > 1:
        for ms, prev in before:
            ms.prev = prev
