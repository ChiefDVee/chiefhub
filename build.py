#!/usr/bin/python3
# ============================================================
# Script Name : build.py
# Author      : Devriendt Chief
# Datum       : 2026-10-18
#
# Genereert de app-kaarten (per sectie: <section> + <h2> + grid) en de JSON-LD in index.html uit apps.json,
# tussen <!-- APPS:START -->/<!-- APPS:END --> en
# <!-- JSONLD:START -->/<!-- JSONLD:END -->, en meta/og/twitter-description (één vaste tekst, max 155,
# niet uit apps.json) tussen <!-- META:START -->/<!-- META:END -->. Statische HTML zodat
# crawlers en AI-fetchers (geen JS) de beschrijvingen zien.
# Idempotent: zelfde apps.json → identieke index.html.
# [2026-11-20] apps.json = {"sections": [{id, title}], "apps": [...]}; elke app heeft een verplicht `section`
# (bekende sectie-id). Volgorde = sectievolgorde, daarbinnen apps.json-volgorde; lege sectie = niet gerenderd.
# JSON-LD volgt dezelfde (getoonde) volgorde.
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
REQUIRED = ("name", "section", "short", "url", "tag", "category", "desc", "points")
SECTION_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
# [2026-11-21] Eén vaste beschrijving voor <meta name="description">, og:description én twitter:description,
# max META_MAX tekens (Google/WhatsApp kappen ±155 af). Bewust NIET uit apps.json: groeit niet mee met nieuwe apps.
META_DESCRIPTION = ("Small tools, no accounts, no strings: free card games, dice games, word puzzles "
                    "and Bitcoin tools by @ChiefXBelgium.")
META_MAX = 155
NAME_PREFIX = "Chief"  # kaarttitel: NAME_PREFIX + <span class="name-accent">rest</span>


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(2)


def load_apps():
    """→ [(section, [apps])] in getoonde volgorde; lege secties vallen weg."""
    try:
        with open(APPS_JSON, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        fail("apps.json: %s" % e)
    if not isinstance(data, dict):
        fail('apps.json must be an object {"sections": [...], "apps": [...]}')
    sections, apps = data.get("sections"), data.get("apps")
    if not isinstance(sections, list) or not sections:
        fail("apps.json: sections must be a non-empty list")
    if not isinstance(apps, list) or not apps:
        fail("apps.json: apps must be a non-empty list")
    ids = []
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict) or not sec.get("id") or not sec.get("title"):
            fail("apps.json sections[%d] needs id + title" % i)
        if not SECTION_ID_RE.match(sec["id"]):
            fail("apps.json sections[%d] id %r: lowercase a-z, 0-9, -" % (i, sec["id"]))
        if sec["id"] in ids:
            fail("apps.json sections[%d] duplicate id %r" % (i, sec["id"]))
        ids.append(sec["id"])
    for i, app in enumerate(apps):
        if not isinstance(app, dict):
            fail("apps.json apps[%d] must be an object" % i)
        missing = [k for k in REQUIRED if not app.get(k)]
        if missing:
            fail("apps.json apps[%d] missing: %s" % (i, ", ".join(missing)))
        if app["section"] not in ids:
            fail("apps.json apps[%d] (%s) unknown section %r (known: %s)" % (i, app["name"], app["section"], ", ".join(ids)))
        if not re.match(r"^https://", app["url"]):
            fail("apps.json apps[%d] url must start with https://" % i)
        if not isinstance(app["points"], list) or not 1 <= len(app["points"]) <= 3:
            fail("apps.json apps[%d] points must be a list of 1-3 strings" % i)
    groups = [(sec, [a for a in apps if a["section"] == sec["id"]]) for sec in sections]
    return [(sec, grp) for sec, grp in groups if grp]


def flat(groups):
    return [a for _, grp in groups for a in grp]


def host(url):
    return re.sub(r"/$", "", re.sub(r"^https?://(www\.)?", "", url))


def render_meta(nl, indent):
    if len(META_DESCRIPTION) > META_MAX:
        fail("META_DESCRIPTION is %d chars (max %d)" % (len(META_DESCRIPTION), META_MAX))
    d = html.escape(META_DESCRIPTION, quote=False).replace('"', "&quot;")  # apostrof letterlijk
    return nl.join([
        indent + '<meta name="description" content="%s">' % d,
        indent + '<meta property="og:description" content="%s">' % d,
        indent + '<meta name="twitter:description" content="%s">' % d,
    ])


def render_name(name):
    """Kaarttitel: "Chief" in --chief-text, rest in --chief-accent (zoals het wordmark).
    Enkel voor de zichtbare kaarttitel (h3 sinds 2026-11-20; h2 = sectiekop); JSON-LD, meta en title blijven de platte naam."""
    e = lambda s: html.escape(s, quote=False)
    if name.startswith(NAME_PREFIX) and len(name) > len(NAME_PREFIX):
        return e(NAME_PREFIX) + '<span class="name-accent">%s</span>' % e(name[len(NAME_PREFIX):])
    return e(name)


def unprefixed(apps):
    return [a["name"] for a in apps if not (a["name"].startswith(NAME_PREFIX) and len(a["name"]) > len(NAME_PREFIX))]


def render_cards(groups, nl, indent):
    e = lambda s: html.escape(s, quote=False)  # text nodes
    a = html.escape                             # attributes
    out = []
    for sec, apps in groups:
        sid = a(sec["id"])
        out += [
            indent + '<section class="apps-section" id="%s" aria-labelledby="%s-title">' % (sid, sid),
            indent + '  <h2 class="section-title" id="%s-title">%s</h2>' % (sid, e(sec["title"])),
            indent + '  <ul class="grid">',
        ]
        i2 = indent + "    "
        for app in apps:
            pts = "".join("<li>%s</li>" % e(p) for p in app["points"])
            out += [
                i2 + "<li>",
                i2 + '  <a class="card" href="%s" rel="noopener">' % a(app["url"]),
                i2 + '    <div class="card-top"><h3>%s</h3><span class="tag">%s</span></div>' % (render_name(app["name"]), e(app["tag"])),
                i2 + "    <p>%s</p>" % e(app["desc"]),
                i2 + '    <ul class="points">%s</ul>' % pts,
                i2 + '    <span class="host">%s</span>' % e(host(app["url"])),
                i2 + "  </a>",
                i2 + "</li>",
            ]
        out += [indent + "  </ul>", indent + "</section>"]
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
    groups = load_apps()
    apps = flat(groups)
    with open(INDEX, encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"
    out = replace_block(src, "APPS", lambda n, i: render_cards(groups, n, i), nl)
    out = replace_block(out, "JSONLD", lambda n, i: render_jsonld(apps, n, i), nl)
    out = replace_block(out, "META", render_meta, nl)
    plain = unprefixed(apps)
    if plain:
        print("NOTE: no '%s' prefix, title rendered plain: %s" % (NAME_PREFIX, ", ".join(plain)))
    if out == src:
        print("index.html up-to-date (%d apps, %d sections)" % (len(apps), len(groups)))
        return 0
    if check:
        print("index.html is stale — run /usr/bin/python3 build.py", file=sys.stderr)
        return 1
    tmp = INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    os.replace(tmp, INDEX)
    print("index.html rebuilt (%d apps, %d sections)" % (len(apps), len(groups)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
