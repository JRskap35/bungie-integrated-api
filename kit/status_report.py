"""The update report: a checklist of every step of the build, what changed, and anything that went wrong (Joe, 2026-11-11).
Usage: python3 -I status_report.py OUT.md OUT.json
Reads build/steps.tsv and build/build.log (kit/build.sh), build/changes.txt (diff.py), build/crosscheck.txt and
build/pvp_rank.txt, plus the workflow's own step results from the environment:
  WORKER, BUILD, EDITOR_BRANCH, PUBLISH, REDIRECT   each step's outcome (success, failure, skipped, cancelled)
  EVENT (schedule, push, workflow_dispatch), RUN_URL, SHA
The workflow adds OUT.md to the run's summary page and opens a GitHub issue with it (see deploy.yml).
OUT.json: {"state": "ok" | "warn" | "fail", "title": ...}."""
import json, os, re, sys
from datetime import datetime, timezone, timedelta

OUT_MD, OUT_JSON = sys.argv[1:3]
rd = lambda p: open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""
env = lambda k: os.environ.get(k, "")
log = rd("build/build.log")
steps = {}
for line in rd("build/steps.tsv").splitlines():
    if "\t" in line: k, v = line.split("\t", 1); steps[k] = v.strip()
# the log, split into the build steps
sec, cur = {}, "start"
for line in log.splitlines():
    m = re.match(r"===== step: (\w+) =====", line)
    if m: cur = m.group(1); continue
    sec.setdefault(cur, []).append(line)
lines = lambda k: sec.get(k, [])
def find(k, pat, fmt=None):
    for l in lines(k):
        m = re.search(pat, l)
        if m: return fmt(m) if fmt else l.strip()
    return None

STEPS = [
    ("sources", "Downloaded every source", "Aegis's sheet, Pride's sheet, Hugo's chart and the Compendium, Bungie's manifest, DIM's wish list, the stored PvP weeks and the live site"),
    ("aegis", "Read and checked Aegis's sheet (PvE)", ""),
    ("pride", "Read Pride's sheet and ran the cross check (PvP)", ""),
    ("hashes", "Matched every weapon to Bungie's item IDs", ""),
    ("pvp", "Counted PvP usage and ranked PvP", ""),
    ("icons", "Added Bungie's icons", ""),
    ("page", "Built the page", ""),
    ("editor", "Built the perk editor", ""),
]
def detail(k):
    d = []
    if k == "sources":
        d.append("Hugo's chart: " + ("saved copy used (live sheet unreachable)" if find(k, r"could not read Hugo") else "read live"))
        v = find(k, r"Bungie manifest (\S+): (\d+) parts reused, (\d+) downloaded", lambda m: f"Bungie manifest {m.group(1)} ({'downloaded' if int(m.group(3)) else 'reused from the last run'})")
        if v: d.append(v)
        d.append("DIM wish list: " + ("not reachable, ranked without creators' picks" if find(k, r"DIM wish list not reachable") else "downloaded"))
        d.append("Stored PvP weeks: " + ("none published yet, used the repo copy" if find(k, r"No published PvP store") else "loaded from the website"))
    elif k == "aegis":
        v = find(k, r"(\d+) weapons in (\d+) sections, (\d+) armor sets", lambda m: f"{m.group(1)} weapons in {m.group(2)} sections, {m.group(3)} armor sets")
        if v: d.append(v)
        if find(k, r"All checks passed"): d.append("All sheet checks passed")
    elif k == "pride":
        v = find(k, r"PvP: (\d+) legendary weapons", lambda m: f"{m.group(1)} PvP weapons on Pride's sheet")
        if v: d.append(v)
        v = find(k, r"(\d+) changes on (\d+) weapons", lambda m: f"Cross check: {m.group(1)} fixes on {m.group(2)} weapons (spellings, columns, perks that can't roll)")
        if v: d.append(v)
        if find(k, r"All cross check rules hold"): d.append("All cross check rules hold")
        v = find(k, r"PvP weapons lined up with Aegis's sheet: (\d+) matched", lambda m: f"{m.group(1)} PvP weapons lined up with Aegis's sections, energy and frames")
        if v: d.append(v)
        v = find(k, r"Moved to Aegis's section: (.*)", lambda m: "moved: " + m.group(1))
        if v: d.append(v)
    elif k == "hashes":
        v = find(k, r"covering (\d+)/(\d+) sheet weapons", lambda m: f"{m.group(1)} of {m.group(2)} weapons found on Bungie")
        if v: d.append(v)
    elif k == "pvp":
        wk = find(k, r"Week starting (\S+):", lambda m: m.group(1))
        d.append(f"New week sampled: the week of {wk}" if wk else "No new week to sample; used the stored weeks")
        v = find(k, r"Weeks counted: \[(.*)\]", lambda m: m.group(1).count("'") // 2)
        if v is not None: d.append(f"{v} of 4 weeks of player data")
        v = find(k, r"PvP use: (\d+) Trials and (\d+) other PvP matches", lambda m: f"{int(m.group(1)):,} Trials and {int(m.group(2)):,} other PvP matches")
        if v: d.append(v)
        v = find(k, r"PvP ranking from players: \d+ weapons, (\d+) rated from play, \d+ perk columns reordered, (\d+) tiers differ", lambda m: f"{m.group(1)} weapons ranked from real play; {m.group(2)} PvP tiers differ from Pride's")
        if v: d.append(v)
        v = find(k, r"Perk editor: (\d+) edited weapons applied", lambda m: f"Perk editor edits applied: {m.group(1)}")
        if v: d.append(v)
    elif k == "icons":
        v = find(k, r"PvP: \d+ weapons .*pictures (\d+)/(\d+)", lambda m: f"PvP weapon pictures {m.group(1)}/{m.group(2)}")
        if v: d.append(v)
    elif k == "page":
        v = find(k, r"([\d.]+ MB) \(website build", lambda m: f"Website page: {m.group(1)}")
        if v: d.append(v)
        if find(k, r"Progress sync on"): d.append("Progress sync connected")
    elif k == "editor":
        v = find(k, r"roll pools for (\d+) weapons", lambda m: f"Roll pools for {m.group(1)} weapons")
        if v: d.append(v)
    return d

ICON = {"ok": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭️"}
issues = []
for k, lst in sec.items():
    for l in lst:
        t = l.strip()
        if re.match(r"(WARNING|STOPPING|PvP sheet check FAILED)", t) or re.match(r"Traceback", t) or re.search(r"\bError\b:", t):
            issues.append((k, t[:400]))
rows, failed_at = [], None
for k, name, sub in STEPS:
    st = steps.get(k)
    warn = [t for kk, t in issues if kk == k and t.startswith("WARNING")]
    if st == "failed": state = "fail"; failed_at = failed_at or name
    elif st == "ok": state = "warn" if warn else "ok"
    else: state = "skip"
    rows.append((state, name, detail(k) if state != "skip" else ["Not run (an earlier step stopped the update)"]))

def wf(key, name, ok_text, fail_text, skip_text="Not run"):
    o = env(key)
    if o == "success": return ("ok", name, [ok_text])
    if o == "failure": return ("fail", name, [fail_text])
    return ("skip", name, [skip_text])
worker_line = "Unchanged, not redeployed" if "Progress sync worker unchanged" in log else "Deployed"
pub = [
    wf("WORKER", "Progress sync service", worker_line, "Deploy failed: saved progress still works from the last deploy", "Skipped (no Cloudflare secrets)"),
    wf("PUBLISH", "Published to endgameapi.pages.dev", "Live", "Cloudflare publish FAILED: the website still shows the last version"),
    wf("REDIRECT", "Old GitHub address forwarding", "Forwards to endgameapi.pages.dev", "Forwarding page not rebuilt"),
    wf("EDITOR_BRANCH", "Perk editor saved for the Update button", "Saved", "Not saved: the editor's Update task can't refresh the editor from this run"),
]
if env("BUILD") == "failure" and not failed_at:
    failed_at = "the build"; rows.append(("fail", "Build", ["Stopped before the first step"]))

all_rows = rows + pub
state = "fail" if any(r[0] == "fail" for r in all_rows) else "warn" if any(r[0] == "warn" for r in all_rows) or issues else "ok"
now = datetime.now(timezone.utc) - timedelta(hours=5)          # US Eastern (standard time); the date is what matters
kind = {"schedule": "Wednesday update", "workflow_dispatch": "Update on demand", "push": "Update after a code change"}.get(env("EVENT"), "Update")
nwarn = sum(1 for _, t in issues if t.startswith("WARNING"))
head = {"ok": "all good", "warn": f"finished with {nwarn or 'some'} warning{'s' if nwarn != 1 else ''}", "fail": f"FAILED at: {failed_at}"}[state]
title = f"{ICON[state]} {kind} · {now.strftime('%a %b %-d, %Y')} · {head}"

# ---------- what changed ----------
ch = rd("build/changes.txt").splitlines()
groups, cur_h = [], None
for l in ch:
    if not l.strip(): continue
    if l.startswith("  "):
        if cur_h is not None: cur_h[1].append(l.strip())
    else: cur_h = [l.strip(), []]; groups.append(cur_h)
summary_lines = []
for h, items in groups:
    hh = re.sub(r"\s*\(\d+\)\s*(<-.*)?$", "", h)
    m = re.match(r"Weapons: (\d+) -> (\d+)\s+Sets: (\d+) -> (\d+)", h)
    if m: summary_lines.append(f"- PvE weapons: {m.group(2)} (was {m.group(1)}) · armor sets: {m.group(4)} (was {m.group(3)})"); continue
    m = re.match(r"PVP WEAPONS: (\d+) -> (\d+)", h)
    if m: summary_lines.append(f"- PvP weapons: {m.group(2)} (was {m.group(1)})"); continue
    if re.match(r"(NEW SETS|REMOVED SETS): \[\]", h): continue
    if re.match(r"(NEW SETS|REMOVED SETS):", h): summary_lines.append(f"- {h.title()}"); continue
    if items: summary_lines.append(f"- **{hh.capitalize().replace('Pvp', 'PvP')}:** {len(items)}")

md = [f"# {title}", ""]
md.append(f"[Open the run]({env('RUN_URL')}) · commit `{env('SHA')[:7]}`" if env("RUN_URL") else "")
if env("PUBLISH") != "success": md += ["", "**The website was not changed.** It still shows the last version that published."]
md += ["", "## Checklist", ""]
for st, name, det in all_rows:
    md.append(f"- {ICON[st]} **{name}**" + (f": {'; '.join(det)}" if det else ""))
md += ["", "## What changed since the last version", ""]
if not ch: md.append("No comparison this time (the live site couldn't be read, or the build stopped first).")
elif not any(items for _, items in groups) and not any(re.match(r"(NEW SETS|REMOVED SETS): \[.+\]", h) for h, _ in groups):
    md.append("Nothing changed on the sheets or in the PvP ranking.")
else:
    md += summary_lines
    full, kept, size = ch, [], 0                                  # GitHub issues hold about 65,000 characters
    for l in full:
        size += len(l) + 1
        if size > 40000: kept.append(f"... and {len(full) - len(kept)} more lines on the run page"); break
        kept.append(l)
    md += ["", "<details><summary>Every change</summary>", "", "```", *kept, "```", "", "</details>"]
md += ["", "## Issues", ""]
if not issues and state != "fail": md.append("None. Every step ran cleanly.")
else:
    names = dict((k, n) for k, n, _ in STEPS)
    for k, t in issues: md.append(f"- {names.get(k, 'Build')}: `{t}`")
    for k, name, _ in STEPS:
        if steps.get(k) == "failed":
            tail = [l for l in lines(k) if l.strip()][-25:]
            md += ["", f"<details open><summary>Last lines from “{name}”</summary>", "", "```", *tail, "```", "", "</details>"]
    for st, name, det in pub:
        if st == "fail": md.append(f"- {name}: {det[0]}")
open(OUT_MD, "w").write("\n".join(md) + "\n")
json.dump({"state": state, "title": title}, open(OUT_JSON, "w"))
print(title)
