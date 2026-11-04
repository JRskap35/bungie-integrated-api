"""Fill the app template with data and images (Bungie-Integrated-API).
Usage: python3 -I assemble.py template.html data.json icons.json OUT.html stat_icons.json ticons.json elements.json brand.json [bungie.json hashes.json]
Without bungie.json the page is built for Claude (sample rolls; progress saves through Claude).
With bungie/config.json ({"apiKey", "clientId"} from bungie.net/en/Application, or nulls until the app is registered)
the page is built as the standalone website: Sign in with Bungie, live weapons from the account, transfers, and a full
HTML document. hashes.json comes from kit/bungie_hashes.py."""
import sys, json
# --editor EDITOR.json builds Joe's perk editor instead (kit/perk_pools.py output; a Claude build with the vault-editor block)
argv = sys.argv[1:]; editor_path = None
if "--editor" in argv: i = argv.index("--editor"); editor_path = argv[i + 1]; del argv[i:i + 2]
sys.argv = [sys.argv[0]] + argv
t, data, icons, out, stat, ticons, elements, brand = sys.argv[1:9]
bungie_path = sys.argv[9] if len(sys.argv) > 9 else None
hashes_path = sys.argv[10] if len(sys.argv) > 10 else None
r = lambda p: open(p, encoding="utf-8").read()
safe = lambda s: s.replace("</", "<\\/")
b = json.load(open(brand))
bcfg = json.load(open(bungie_path)) if bungie_path else None
site = bungie_path is not None
ready = bool(bcfg and bcfg.get("apiKey") and bcfg.get("clientId"))
html = r(t)
for key, val in (("__DATA__", safe(r(data))), ("__ICONS__", safe(r(icons))), ("__STATICONS__", safe(r(stat))),
                 ("__TICONS__", safe(r(ticons))), ("__ELEMENTS__", safe(r(elements))), ("__FIREBASE__", "null"),
                 ("__BUNGIE__", json.dumps(bcfg if ready else None)), ("__HASHES__", safe(r(hashes_path)) if hashes_path else "null"),
                 ("__EDITOR__", safe(r(editor_path)) if editor_path else "null"), ("__LOGO__", b["logo"]), ("__BG__", b["bg"]), ("__SOUND__", json.dumps(b.get("sound")))):
    assert html.count(key) == 1, key
    html = html.replace(key, val, 1)
if editor_path: html = html.replace("<title>Endgame API</title>", "<title>Perk Editor</title>", 1)
if site:
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="description" content="Destiny 2 god roll tracker that reads your Bungie account: every copy graded for PvE and PvP, new drops, and transfers.">'
            '<meta name="theme-color" content="#0c0e10">'
            f'<link rel="icon" href="{b["logo"]}"><link rel="apple-touch-icon" href="{b["logo"]}">'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
            'body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>'
            '</head><body>')
    html = head + html + "</body></html>"
open(out, "w", encoding="utf-8").write(html)
print(round(len(html) / 1e6, 2), "MB", ("(website build, Sign in with Bungie on)" if ready else "(website build, Bungie app not registered yet: sample rolls)") if site else "(Claude build)")
