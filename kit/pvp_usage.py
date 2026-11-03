"""What PvP players actually use, read from Bungie's own match reports, for pvp_rank.py (Joe, 2026-11-03).
Usage: python3 -I pvp_usage.py hashes.json bungie/config.json PREV_URL SEED.json OUT_usage.json OUT_perks.json OUT_store.json

Every weekly reset (Tuesday 17:00 UTC) closes a week. For each of the last four closed weeks that the store doesn't have
yet, this samples Bungie's post game carnage reports from that week (random report ids, the PvP ones kept), and for
every weapon on the sheets adds up kills in Trials and in the rest of PvP, how many players got kills with it, and how
many of those players won. For the newest week it also reads the public loadouts of players from those matches and,
for each weapon they got kills with that is still equipped, the perks, barrel, magazine, masterwork and origin trait
on it. Weeks already counted come from the store the last build published with the site (PREV_URL), or from the copy
kept in the repo (SEED.json) the first time. Writes:
  OUT_usage.json  totals over the last four closed weeks, week 0 the newest (pvp_rank.py reads it)
  OUT_perks.json  equipped parts per weapon, summed over the weeks that have loadouts
  OUT_store.json  the per week store, published as pvp_usage.json for the next build
If Bungie can't be reached the stored weeks are used as they are, so a Bungie outage never stops the update.
Environment: PVP_SAMPLE (reports per week, default 30000), PVP_PLAYERS (loadouts to read, default 9000),
PVP_BUDGET (seconds for the whole step, default 1800)."""
import json, os, sys, ssl, time, random, collections, subprocess, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

HASHES, CONFIG, PREV_URL, SEED, OUT_USAGE, OUT_PERKS, OUT_STORE = sys.argv[1:8]
H = json.load(open(HASHES)); CFG = json.load(open(CONFIG))
KEY = CFG["apiKey"]; ORIGIN = CFG.get("bungieOrigin") or "https://endgameapi.pages.dev"
SAMPLE = int(os.environ.get("PVP_SAMPLE", 30000)); PLAYERS = int(os.environ.get("PVP_PLAYERS", 9000))
DEADLINE = time.time() + int(os.environ.get("PVP_BUDGET", 1800))
WEEKS = 4; THREADS = 24
CTX = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"]) if os.environ.get("SSL_CERT_FILE") else ssl.create_default_context()

def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"X-API-Key": KEY, "Origin": ORIGIN, "User-Agent": "endgame-api-weekly-build"})
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try: body = json.loads(e.read())
            except Exception: body = None
            if e.code in (429, 500, 502, 503, 504) or (body and body.get("ErrorCode") in (36, 51)):   # throttled or busy
                time.sleep(1.5 * (i + 1) + random.random()); continue
            return body
        except Exception:
            time.sleep(1 + i)
    return None
def pgcr(i):
    r = get(f"https://stats.bungie.net/Platform/Destiny2/Stats/PostGameCarnageReport/{i}/")
    return r["Response"] if r and r.get("ErrorCode") == 1 else None
def when(R): return datetime.strptime(R["period"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)

# ---------- report ids and time: ids rise with time, about 50,000 an hour, with gaps
def probe(i):
    for k in (0, 3, 11, 29, 71):
        R = pgcr(i + k)
        if R: return R
    return None
def newest_id():
    lo, hi = 16_000_000_000, 40_000_000_000
    while hi - lo > 200:
        mid = (lo + hi) // 2
        if probe(mid): lo = mid
        else: hi = mid
    return lo
def id_at(t, lo, hi):
    """the first report id played at or after time t (between lo and hi)"""
    while hi - lo > 2000:
        mid = (lo + hi) // 2; R = probe(mid)
        if R is None or when(R) >= t: hi = mid
        else: lo = mid
    return hi

def last_reset(now):
    r = now.replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(days=(now.weekday() - 1) % 7)
    return r if r <= now else r - timedelta(days=7)

# ---------- one week: sampled PvP reports counted per weapon
def key_of(h):
    k = H["w"].get(str(h)); return (k if isinstance(k, str) else k[0]) if k else None
def empty_week():
    return {"S": {}, "TOT": {"trials": 0, "crucible": 0}, "MATCH": {"trials": 0, "crucible": 0}, "sampled": 0, "perks": None}
def count(week, R, players):
    g = "trials" if 84 in R["activityDetails"].get("modes", []) else "crucible"; week["MATCH"][g] += 1
    for e in R["entries"]:
        v = e.get("values", {}); won = v.get("standing", {}).get("basic", {}).get("value") == 0
        used = []
        for wp in (e.get("extended") or {}).get("weapons", []):
            kills = wp["values"]["uniqueWeaponKills"]["basic"]["value"]; week["TOT"][g] += kills
            k = key_of(wp["referenceId"])
            if not k or kills <= 0: continue
            s = week["S"].setdefault(k, {"k": {}, "u": {}, "win": {}})
            s["k"][g] = s["k"].get(g, 0) + kills; s["u"][g] = s["u"].get(g, 0) + 1; s["win"][g] = s["win"].get(g, 0) + won
            used.append(str(wp["referenceId"]))
        u = e["player"]["destinyUserInfo"]
        if players is not None and used and u.get("membershipId"):
            players.setdefault((u["membershipType"], u["membershipId"]), set()).update(used)
def sample_week(lo, hi, players):
    week = empty_week(); rnd = random.Random(lo)
    ids = rnd.sample(range(lo, hi), min(SAMPLE, hi - lo)); t0 = time.time()
    with ThreadPoolExecutor(THREADS) as ex:
        for i in range(0, len(ids), 2000):
            if time.time() > DEADLINE - 600: print("  stopping early to stay inside the time budget"); break
            for R in ex.map(pgcr, ids[i:i + 2000]):
                week["sampled"] += 1
                if R and 5 in R["activityDetails"].get("modes", []): count(week, R, players)
    print(f"  {week['sampled']} reports in {time.time() - t0:.0f}s: {week['MATCH']['trials']} Trials, {week['MATCH']['crucible']} other PvP")
    return week

# ---------- loadouts: equipped parts on the weapons each player got kills with
def loadout(item):
    (mt, mid), hashes = item
    p = get(f"https://www.bungie.net/Platform/Destiny2/{mt}/Profile/{mid}/?components=205,305")
    if not p or p.get("ErrorCode") != 1: return []
    R = p["Response"]; eq = (R.get("characterEquipment") or {}).get("data") or {}
    sk = ((R.get("itemComponents") or {}).get("sockets") or {}).get("data") or {}
    out = []
    for inv in eq.values():
        for it in inv.get("items", []):
            h = str(it["itemHash"])
            if h not in hashes: continue
            s = (sk.get(it.get("itemInstanceId", "")) or {}).get("sockets", [])
            out.append((key_of(h), [H["p"][str(x.get("plugHash"))] for x in s if str(x.get("plugHash")) in H["p"]]))
    return out
def read_perks(players):
    P = {}
    items = list(players.items()); random.Random(7).shuffle(items); items = items[:PLAYERS]; t0 = time.time()
    with ThreadPoolExecutor(THREADS) as ex:
        for res in ex.map(loadout, items):
            for k, plugs in res:
                if not k or not plugs: continue
                a = P.setdefault(k, {"n": 0, "c1": {}, "c2": {}, "barrel": {}, "mag": {}, "mw": {}, "origin": {}, "combo": {}})
                a["n"] += 1; perks = [n for n, kd in plugs if kd == "perk"]
                inc = lambda f, n: a[f].__setitem__(n, a[f].get(n, 0) + 1)
                if perks: inc("c1", perks[0])
                if len(perks) > 1: inc("c2", perks[1]); inc("combo", perks[0] + " + " + perks[1])
                for n, kd in plugs:
                    if kd in ("barrel", "mag", "mw", "origin"): inc(kd, n)
    print(f"  {len(items)} loadouts in {time.time() - t0:.0f}s, {sum(a['n'] for a in P.values())} weapon copies")
    return P

# ---------- the store: weeks already counted
def load_prev():
    try:
        page = subprocess.run(["curl", "-sSfL", "--max-time", "60", PREV_URL], capture_output=True, check=True).stdout
        st = json.loads(page); print(f"Previous store from {PREV_URL}: {sorted(st.get('weeks', {}))}"); return st
    except Exception as e:
        print(f"No store at {PREV_URL} ({e.__class__.__name__}); using the repo copy {SEED}")
        try: return json.load(open(SEED))
        except Exception: return {"weeks": {}}

store = load_prev(); weeks = store.setdefault("weeks", {})
now = datetime.now(timezone.utc); r0 = last_reset(now)
want = [(r0 - timedelta(days=7 * (i + 1)), r0 - timedelta(days=7 * i)) for i in range(WEEKS)]   # newest first
names = [a.strftime("%Y-%m-%d") for a, _ in want]
todo = [(n, a, b) for n, (a, b) in zip(names, want) if n not in weeks]
if todo:
    try:
        top = newest_id(); print(f"Newest Bungie match report id {top}")
        for n, a, b in todo:
            if time.time() > DEADLINE - 600: print(f"Out of time before week {n}"); break
            lo = id_at(a, top - 60_000_000, top); hi = id_at(b, lo, top)
            print(f"Week starting {n}: report ids {lo} to {hi}")
            players = {} if n == names[0] else None
            wk = sample_week(lo, hi, players)
            if players: wk["perks"] = read_perks(players)
            weeks[n] = wk
    except Exception as e:
        print(f"WARNING: Bungie match reports could not be read ({e}); using the stored weeks")
for n in list(weeks):
    if n not in names: del weeks[n]                        # older than four closed weeks
have = [n for n in names if n in weeks]
print(f"Weeks counted: {have}")

# ---------- totals for pvp_rank.py (week 0 = newest)
U = {"S": {}, "TOT": {"trials": 0, "crucible": 0}, "MATCH": {"trials": 0, "crucible": 0}, "WEEKTOT": {}, "from": names[-1], "to": r0.strftime("%Y-%m-%d")}
for wi, n in enumerate(names):
    wk = weeks.get(n)
    if not wk: U["WEEKTOT"][str(wi)] = 0; continue
    U["WEEKTOT"][str(wi)] = wk["TOT"]["trials"] + wk["TOT"]["crucible"]
    for g in ("trials", "crucible"): U["TOT"][g] += wk["TOT"][g]; U["MATCH"][g] += wk["MATCH"][g]
    for k, s in wk["S"].items():
        t = U["S"].setdefault(k, {"k": {}, "u": {}, "win": {}, "wk": {}})
        for f in ("k", "u", "win"):
            for g, v in s[f].items(): t[f][g] = t[f].get(g, 0) + v
        t["wk"][str(wi)] = t["wk"].get(str(wi), 0) + sum(s["k"].values())
P = {}
for n in have:
    for k, a in (weeks[n].get("perks") or {}).items():
        b = P.setdefault(k, {"n": 0, "c1": {}, "c2": {}, "barrel": {}, "mag": {}, "mw": {}, "origin": {}, "combo": {}})
        b["n"] += a["n"]
        for f in ("c1", "c2", "barrel", "mag", "mw", "origin", "combo"):
            for x, v in a.get(f, {}).items(): b[f][x] = b[f].get(x, 0) + v
json.dump(U, open(OUT_USAGE, "w")); json.dump(P, open(OUT_PERKS, "w")); json.dump(store, open(OUT_STORE, "w"), separators=(",", ":"))
print(f"PvP use: {U['MATCH']['trials']} Trials and {U['MATCH']['crucible']} other PvP matches over {len(have)} weeks, "
      f"{sum(a['n'] for a in P.values())} equipped weapon copies")
if not have: print("WARNING: no PvP use data at all; pvp_rank.py keeps Pride's tiers")
