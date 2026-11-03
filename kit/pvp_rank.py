"""PvP tiers and perk order from what players actually use (Joe, 2026-11-03).
Usage: python3 -I pvp_rank.py data.json pride.json usage.json perks.json wishlist.txt hashes.json OUT.json REPORT.txt

data.json      the build's data (its pvp section is rewritten)
pride.json     the same data straight from Pride's sheet (pvp.py output), for Pride's own perk lists and tiers
usage.json     kills per weapon from Bungie match reports (pvp_usage.py): Trials and Crucible, players, wins, by week
perks.json     equipped parts of players who got PvP kills with each weapon (pvp_usage.py)
wishlist.txt   DIM's community wish list (PvP rolls by Pandapaxxy, Mercules, YeezyGT, Legoleflash and others)
hashes.json    Bungie item and plug hashes to the sheet's weapon keys and part names (bungie_hashes.py)

Tier, per weapon section (Autos, Hand Cannons, Shotguns, ...): each weapon's share of all weapon kills, 60% Trials and
40% Crucible, times a small win rate factor (pulled toward 50% for small samples) and a consistency factor (weeks used
out of four, and how steady the weekly share was). Weapons with enough players are ranked; the top 10% of the section
is S, then 15% A, 20% B, 25% C, the rest D. Enough players means 30 for primaries, 15 for special and 10 for heavy
weapons. Weapons too few players use keep Pride's tier but cannot sit above C
(B and below drop one step). Hugo's kill times no longer move tiers.
Perks, per column: 3.0 x share of players' copies running it (scaled down under 25 copies) + 0.6 if Pride lists it +
0.6 x share of creators who picked it + 0.3 if it lowers the kill time in a first duel (Headseeker, Opening Shot,
Explosive Payload, Timed Payload, Precision Instrument). The top three stay. Barrels, magazines and masterworks keep
Pride's picks, ordered by what players run, and add the players' favourite when at least a quarter of copies use it."""
import json, re, sys, collections, statistics
DATA, PRIDE, USAGE, PERKS, WISH, HASHES, OUT, REPORT = sys.argv[1:9]
d = json.load(open(DATA)); pr = json.load(open(PRIDE)); U = json.load(open(USAGE)); PK = json.load(open(PERKS)); H = json.load(open(HASHES))
nn = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("’", "'"))
pname = lambda x: x[0] if isinstance(x, list) else x
live = lambda a: [x for x in (a or []) if not isinstance(x, list)]
key = lambda w: w["arch"] + "|" + nn(w["name"])
TIERS = "SABCDEF"; CAP = {"p1": 3, "p2": 3, "barrel": 2, "mag": 2}
DUEL = {"headseeker", "openingshot", "explosivepayload", "timedpayload", "precisioninstrument"}
CUTS = [(.10, "S"), (.25, "A"), (.45, "B"), (.70, "C"), (1.01, "D")]
TOT, WEEKTOT = U["TOT"], U["WEEKTOT"]
mwkey = lambda n: re.sub(r"\s+speed$", "", re.sub(r"^(masterworked:|tier\s*\d+\s*:)\s*", "", (n or "").strip().lower()))

# ---- community creators' PvP picks per weapon and column
comm = collections.defaultdict(lambda: {"src": set(), "cols": [collections.defaultdict(set), collections.defaultdict(set)]})
title = notes = ""
for l in open(WISH, encoding="utf-8", errors="replace"):
    l = l.rstrip("\n")
    if l.startswith("title:"): title = l[6:].strip()
    elif l.startswith("//notes:"): notes = l
    elif l.startswith("dimwishlist:"):
        txt = notes + " " + l
        if not re.search(r"\bPvP\b", txt) or re.search(r"\(PvE\b", txt): continue
        m = re.search(r"item=(-?\d+)&perks=([\d,]+)", l); k = m and H["w"].get(m.group(1))
        if not k: continue
        k = k if isinstance(k, str) else k[0]
        traits = [H["p"][p][0] for p in m.group(2).split(",") if p in H["p"] and H["p"][p][1] == "perk"]
        if not traits: continue
        comm[k]["src"].add(title)
        for i, t in enumerate(traits[:2]): comm[k]["cols"][i][t].add(title)

def usage(k):
    s = U["S"].get(k)
    if not s: return None
    g = lambda f, m: s.get(f, {}).get(m, 0)
    users = g("u", "trials") + g("u", "crucible"); wins = g("win", "trials") + g("win", "crucible")
    weekly = [s.get("wk", {}).get(str(w), 0) / max(1, WEEKTOT[str(w)]) * 100 for w in range(4)]
    mean = statistics.mean(weekly); cv = statistics.pstdev(weekly) / mean if mean else 9
    return {"t": round(g("k", "trials") / TOT["trials"] * 100, 3), "c": round(g("k", "crucible") / TOT["crucible"] * 100, 3),
            "users": users, "win": round(wins / users, 3) if users else None, "weeks": sum(1 for x in weekly if x > 0), "cv": round(cv, 2)}
def pscore(u):
    if not u: return 0.0
    w = (u["users"] * (u["win"] or .5) + 60 * .5) / (u["users"] + 60)
    return (0.6 * u["t"] + 0.4 * u["c"]) * (1 + 1.5 * (w - .5)) * (u["weeks"] / 4) * (1 - min(.4, u["cv"] / 3))

pride_by = {w["id"]: w for w in pr["pvp"]["weapons"]}
PW = d["pvp"]["weapons"]; report = []; perk_changes = 0
for w in PW:
    k = key(w); p0 = pride_by.get(w["id"], w); u = usage(k); w["use"] = u; w["_ps"] = pscore(u)
    w.setdefault("pr", [p0.get("tier"), p0.get("rank")])
    pk = PK.get(k) or {}; n = pk.get("n", 0); conf = min(1.0, n / 25); c = comm.get(k); ns = len(c["src"]) if c else 0
    tt = (w.get("ttk") or {}); base = tt.get("base"); fast = {nn(p): t for p, t in (tt.get("perks") or {}).items() if nn(p) in DUEL and base and t < base - 1e-6}
    for i, f in enumerate(("p1", "p2")):
        pride = [pname(x) for x in live(p0.get(f))]
        cand = collections.OrderedDict((nn(x), x) for x in pride)
        cnt = pk.get("c%d" % (i + 1), {})
        if c:
            for x in c["cols"][i]: cand.setdefault(nn(x), x)
        for x, m in cnt.items():
            if m >= max(3, 0.08 * n): cand.setdefault(nn(x), x)
        rows = []
        for kk, x in cand.items():
            m = next((v for nm, v in cnt.items() if nn(nm) == kk), 0)
            s = 3.0 * conf * (m / n if n else 0) + (0.6 if kk in {nn(y) for y in pride} else 0) \
                + 0.6 * (len(c["cols"][i].get(x, ())) / ns if c and ns else 0) + (0.3 if kk in fast else 0)
            rows.append((-s, -m, pride.index(x) if x in pride else 99, x))
        new = [x for *_, x in sorted(rows)][:CAP[f]]
        if [pname(x) for x in live(w.get(f))] != new: perk_changes += 1
        w[f] = new
    for f in ("barrel", "mag"):
        cnt = pk.get(f, {}); pride = [pname(x) for x in live(p0.get(f))]
        top = max(cnt.items(), key=lambda kv: kv[1]) if cnt else None
        lst = pride + ([top[0]] if top and n >= 10 and top[1] >= 0.25 * n and nn(top[0]) not in {nn(x) for x in pride} else [])
        lst = [x for _, _, x in sorted((-next((v for nm, v in cnt.items() if nn(nm) == nn(x)), 0), j, x) for j, x in enumerate(lst))]
        w[f] = lst[:CAP[f]]
    cnt = collections.Counter()
    for nm, v in pk.get("mw", {}).items(): cnt[mwkey(nm)] += v
    mws = [x.strip() for x in (p0.get("mw") or "").split("/") if x.strip()]
    top = cnt.most_common(1)[0] if cnt else None
    if top and n >= 10 and top[1] >= 0.3 * n and top[0] not in {mwkey(x) for x in mws}:
        mws.append(next((nm for nm in pk["mw"] if mwkey(nm) == top[0]), top[0]).split(": ")[-1])
    mws = [x for _, _, x in sorted((-cnt.get(mwkey(x), 0), j, x) for j, x in enumerate(mws))]
    w["mw"] = " / ".join(mws[:2])
    # the TTK box follows the finished lists: only perks listed here that speed up a first duel count
    if tt and base:
        listed = {nn(x) for x in w["p1"] + w["p2"]}
        keep = {p: t for p, t in (tt.get("perks") or {}).items() if nn(p) in listed and nn(p) in DUEL and t < base - 1e-6}
        best = min([base] + list(keep.values()))
        w["ttk"] = dict(tt, perks=keep, best=best, by=[p for p, t in keep.items() if abs(t - best) < 1e-6])
    w["play"] = {"n": n, "combos": [[c2, v] for c2, v in sorted(pk.get("combo", {}).items(), key=lambda kv: -kv[1])[:3]]} if n else None

# ---- tiers per section
moved = []
for arch in sorted({w["arch"] for w in PW}):
    ws = [w for w in PW if w["arch"] == arch]
    # enough players to rate from play: special and heavy weapons get fewer PvP kills, so their bar is lower
    ammo = next((a for a, archs in d["pvp"].get("ammo", {}).items() if arch in archs), "primary")
    need = {"primary": 30, "special": 15}.get(ammo, 10)
    rated = sorted([w for w in ws if w["use"] and w["use"]["users"] >= need], key=lambda w: -w["_ps"])
    for i, w in enumerate(rated):
        w["tier"] = next(t for c, t in CUTS if (i + 0.5) / len(ws) < c); w["tierBy"] = "players"
    for w in ws:
        if w.get("tierBy") != "players":
            e = TIERS.index(w["pr"][0] or "C")
            w["tier"] = TIERS[3 if e <= 1 else min(6, max(e, 3) + 1)]; w["tierBy"] = "few players"
    for i, w in enumerate(sorted(ws, key=lambda w: (TIERS.index(w["tier"]), -w["_ps"], w["pr"][1] or 99)), 1):
        w["rank"] = i
        if w["tier"] != w["pr"][0]: moved.append(f"{w['name']} ({arch}) {w['pr'][0]} to {w['tier']}")
for w in PW: w.pop("_ps", None)
d["pvp"]["rank"] = {"matches": U["MATCH"], "copies": sum(v.get("n", 0) for v in PK.values()), "from": U.get("from", ""), "to": U.get("to", "")}
json.dump(d, open(OUT, "w"), ensure_ascii=False)
with open(REPORT, "w") as f:
    f.write(f"PvP ranking from players: {len(PW)} weapons, {sum(1 for w in PW if w['tierBy'] == 'players')} rated from play, "
            f"{perk_changes} perk columns reordered, {len(moved)} tiers differ from Pride's\n" + "; ".join(moved) + "\n")
print(open(REPORT).read()[:400])
