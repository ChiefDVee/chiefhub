#!/usr/bin/python3
# ============================================================
# Script Name : build.py
# Author      : Devriendt Chief
# Datum       : 2026-10-18
#
# Genereert de app-kaarten en de JSON-LD in index.html uit apps.json,
# tussen <!-- APPS:START -->/<!-- APPS:END --> en
# <!-- JSONLD:START -->/<!-- JSONLD:END -->. Statische HTML zodat
# crawlers en AI-fetchers (geen JS) de beschrijvingen zien.
# Idempotent: zelfde apps.json → identieke index.html.
#
# Gebruik : /usr/bin/python3 build.py [--check]
#           --check = enkel controleren of index.html up-to-date is
# Exit    : 0 = ok/up-to-date, 1 = --check: index.html verouderd,
#           2 = apps.json of markers ongeldig
# ============================================================
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APPS_JSON = os.path.join(HERE, "apps.json")
INDEX = os.path.join(HERE, "index.html")
REQUIRED = ("name", "url", "tag", "category", "desc", "points")


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(2)


def load_apps():
    try:
        with open(APPS_JSON, encoding="utf-8") as f:
            apps = json.load(f)
    except (OSError, ValueError) as e:
        fail("apps.json: %s" % e)
    if not isinstance(apps, list) or not apps:
        fail("apps.json must be a non-empty list")
    for i, app in enumerate(apps):
        missing = [k for k in REQUIRED if not app.get(k)]
        if missing:
            fail("apps.json[%d] missing: %s" % (i, ", ".join(missing)))
        if not re.match(r"^https://", app["url"]):
            fail("apps.json[%d] url must start with https://" % i)
        if not isinstance(app["points"], list) or not 1 <= len(app["points"]) <= 3:
            fail("apps.json[%d] points must be a list of 1-3 strings" % i)
    return apps


def host(url):
    return re.sub(r"/$", "", re.sub(r"^https?://", "", url))


def render_cards(apps, nl, indent):
    e = lambda s: html.escape(s, quote=False)  # text nodes
    a = html.escape                             # attributes
    out = []
    for app in apps:
        pts = "".join("<li>%s</li>" % e(p) for p in app["points"])
        out += [
            indent + "<li>",
            indent + '  <a class="card" href="%s" rel="noopener">' % a(app["url"]),
            indent + '    <div class="card-top"><h2>%s</h2><span class="tag">%s</span></div>' % (e(app["name"]), e(app["tag"])),
            indent + "    <p>%s</p>" % e(app["desc"]),
            indent + '    <ul class="points">%s</ul>' % pts,
            indent + '    <span class="host">%s</span>' % e(host(app["url"])),
            indent + "  </a>",
            indent + "</li>",
        ]
    return nl.join(out)


def render_jsonld(apps, nl, indent):
    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Chief's Tools",
        "url": "https://chiefke.com/",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "item": {
                    "@type": "SoftwareApplication",
                    "name": app["name"],
                    "url": app["url"],
                    "description": app["desc"],
                    "applicationCategory": app["category"],
                    "operatingSystem": "Web",
                    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
                },
            }
            for i, app in enumerate(apps)
        ],
    }
    body = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    lines = ['<script type="application/ld+json">'] + body.split("\n") + ["</script>"]
    return nl.join(indent + l for l in lines)


def replace_block(src, name, render, nl):
    pat = re.compile(r"(<!-- %s:START -->)(.*?)(\n?)([ \t]*)(<!-- %s:END -->)" % (name, name), re.S)
    matches = pat.findall(src)
    if len(matches) != 1:
        fail("index.html: expected exactly 1 %s:START/END marker pair, found %d" % (name, len(matches)))
    indent = pat.search(src).group(4)
    return pat.sub(lambda m: m.group(1) + nl + render(nl, indent) + nl + indent + m.group(5), src)


def main():
    check = "--check" in sys.argv[1:]
    apps = load_apps()
    with open(INDEX, encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"
    out = replace_block(src, "APPS", lambda n, i: render_cards(apps, n, i), nl)
    out = replace_block(out, "JSONLD", lambda n, i: render_jsonld(apps, n, i), nl)
    if out == src:
        print("index.html up-to-date (%d apps)" % len(apps))
        return 0
    if check:
        print("index.html is stale — run /usr/bin/python3 build.py", file=sys.stderr)
        return 1
    tmp = INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    os.replace(tmp, INDEX)
    print("index.html rebuilt (%d apps)" % len(apps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
