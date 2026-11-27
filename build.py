#!/usr/bin/python3
# ============================================================
# Script Name : build.py
# Author      : Devriendt Chief
# Datum       : 2026-10-18
# Last Run    : $(date +'%Y-%m-%d %H:%M:%S')
#
# NOTICE: Internal System Chiefbase/Chiefmobile.
# APOCALYPSE WARNING: Apocalypse alert if misconfigured.
# © Devriendt Chief – Private Internal Tool
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
# [2026-11-26] Updates ronde 2: leest LOKAAL alle changelog-JSON's (CHANGELOGS hieronder = de enige plek met de paden,
# ook die in de andere repo's: ../16_CHIEFJINX/… enz.), valideert ze (chief_updates.py, kopie per repo) en schrijft:
#   - index.html tussen <!-- LATEST:START -->/<!-- LATEST:END -->: blok "Latest updates" = max. één entry per spel
#     (de nieuwste; gelijke datum → de eerste in het bestand), datum aflopend (gelijke datum → spelnaam), de LATEST_N
#     bovenste, met spelnaam + link naar de updates-pagina; enkel Engels; geen runtime-requests (statische HTML);
#     [2026-11-26] was eerst de LATEST_N nieuwste entries over alle spellen (één spel kon het blok vullen);
#   - dice/updates/index.html en bingo/updates/index.html ("What's new", Engels zoals het spel) volledig, behalve het
#     footerblok tussen de CHIEF-FOOTER-markers (dat blijft van chief-brand-sync en wordt overgenomen);
#   - in dice/ en bingo/index.html tussen <!-- UPDLINK:START -->/<!-- UPDLINK:END --> (in de ?-sheet): link "What's new" +
#     updates.js met data-latest (bolletje op ?).
#   Ontbreekt of faalt een bronbestand → luid falen (exit 2), ook bij --check.
#
# [2026-11-27] Doelmodus (chiefke-app ronde A): --target chiefke --out <map> [--urlmap <mounts.json>] schrijft een
# VOLLEDIGE kopie van de hub voor www.chiefke.com in <map> (nooit in deze repo): dice/ bingo/ qotd/ → chiefdice/
# chiefbingo/ chiefqotd/, elke product-URL (oud domein) → https://www.chiefke.com/chief<naam>/…, chiefke.com en
# fees.chiefke.com → www.chiefke.com(/chieffees/), root-paden "/dice/" → "/chiefdice/", sitemap.xml → sitemap-hub.xml
# (de app serveert /sitemap.xml als index en /robots.txt zelf). Bron van oud → nieuw = de mountmap van de chiefke-repo
# (standaard ../21_CHIEFKE/chiefke/mounts.json: "origin", "products", "sites"); geen tweede kopie hier.
# Gegenereerde blokken komen uit dezelfde generatie als de Pages-build (kaarten met de nieuwe URL's, zodat ook de
# getoonde host klopt). Schrijven per bestand atomisch; bestanden die niet meer in de uitvoer horen worden gemeld,
# nooit gewist. Zonder --target: exact het gedrag van vroeger (Pages-uitvoer byte-identiek, guard in de chiefke-tests).
# [2026-11-27, ronde B] Links BINNEN de site zijn in de doelmodus pad-relatief vanaf de root (href/src/action in HTML:
# https://www.chiefke.com/chiefdaily/ → /chiefdaily/), zodat ze op elke host werken (testhost, lokaal, www). Enkel
# canonical en <link rel=alternate>, og:*, twitter:*, JSON-LD, sitemaps en de QOTD-deellink (permalink) blijven
# absoluut https://www.chiefke.com/… (guard: 21_CHIEFKE/tests/test_sitebuild.py scant alle HTML van de doelbuild).
# [2026-11-27, ronde C] Productstatus uit de mountmap (products.<n>.status): enkel "live"-producten worden naar
# /chief<naam>/ herschreven. "legacy"-producten (draaien nog op hun oude domein) houden in de doelbuild hun oude URL
# (kaart, getoonde host, Latest updates, JSON-LD) — zo linkt de hub niet naar een 302 en klapt hij in ronde D vanzelf
# om (status → live + deploy = sitebuild). Status ontbreekt of ongeldig = exit 2. Pages-uitvoer ongewijzigd.
# Gebruik : /usr/bin/python3 build.py [--check]
#           /usr/bin/python3 build.py --target chiefke --out <map> [--urlmap <pad>] [--check]
#           --check = enkel controleren of index.html, het Latest-blok, de UPDLINK-blokken en de updates-pagina's
#           up-to-date zijn (met --target: of <map> exact de doeluitvoer bevat)
# Exit    : 0 = ok/up-to-date, 1 = --check: iets verouderd,
#           2 = apps.json, markers, een changelog of de urlmap ongeldig/ontbrekend, of usage
# ============================================================
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chief_updates  # noqa: E402  (kopie per repo, zelfde inhoud)

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
# [2026-11-26] Changelogs: (id, spelnaam, pad t.o.v. 14_CHIEFHUB, updates-URL, eigen pagina op chiefke.com of None).
# Eén config voor alle paden; tie-break bij gelijke datum in "Latest updates" = spelnaam (niet deze volgorde).
CHANGELOGS = (
    ("jinx", "ChiefJINX", "../16_CHIEFJINX/chiefjinx/web/changelog/jinx.json", "https://www.chiefjinx.com/updates/", None),
    ("yatzy", "ChiefYatzy", "../17_CHIEFYATZY/chiefyatzy/web/changelog/yatzy.json", "https://www.chiefyatzy.com/updates/", None),
    ("pairs", "ChiefPairs", "../18_CHIEFSHUFFLE/chiefshuffle/web/changelog/pairs.json", "https://www.chiefshuffle.com/pairs/updates/", None),
    ("rami", "ChiefRami", "../18_CHIEFSHUFFLE/chiefshuffle/web/changelog/rami.json", "https://www.chiefshuffle.com/rami/updates/", None),
    ("mahjong", "ChiefMahjong", "../18_CHIEFSHUFFLE/chiefshuffle/web/changelog/mahjong.json",
     "https://www.chiefshuffle.com/mahjong/updates/", None),
    ("solitaire", "ChiefSolitaire", "../18_CHIEFSHUFFLE/chiefshuffle/web/changelog/solitaire.json",
     "https://www.chiefshuffle.com/solitaire/updates/", None),
    ("words", "ChiefWords", "../20_CHIEFLETTERS/chiefletters/web/changelog/words.json", "https://www.chiefletters.com/words/updates/", None),
    ("daily", "ChiefDaily", "../20_CHIEFLETTERS/chiefletters/web/changelog/daily.json", "https://www.chiefletters.com/daily/updates/", None),
    ("count", "ChiefCount", "../09_CHIEFCOUNT/changelog/count.json", "https://www.chiefcount.com/updates/", None),
    ("dice", "ChiefDice", "changelog/dice.json", "https://chiefke.com/dice/updates/", "dice"),
    ("bingo", "ChiefBingo", "changelog/bingo.json", "https://chiefke.com/bingo/updates/", "bingo"),
)
LATEST_N = 6
# basis voor de relatieve CHANGELOGS-paden; CHIEF_HUB_CHANGELOG_BASE enkel voor tests (build op een kopie in 05_TMP)
CHANGELOG_BASE = os.environ.get("CHIEF_HUB_CHANGELOG_BASE") or HERE
FOOTER_RE = re.compile(r"<!-- CHIEF-FOOTER:START -->.*?<!-- CHIEF-FOOTER:END -->", re.S)
EMPTY_FOOTER = "<!-- CHIEF-FOOTER:START -->\n<!-- CHIEF-FOOTER:END -->"


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


def load_changelogs():
    """→ [(cfg, data)] in CHANGELOGS-volgorde; ontbrekend of ongeldig → fail (exit 2)."""
    out = []
    for cfg in CHANGELOGS:
        gid, name, rel, url, own = cfg
        path = os.path.normpath(os.path.join(CHANGELOG_BASE, rel))
        if not os.path.isfile(path):
            fail("changelog %s ontbreekt: %s" % (gid, path))
        try:
            data = chief_updates.load(path, gid)
        except chief_updates.ChangelogError as exc:
            fail(str(exc))
        out.append((cfg, data))
    return out


def latest_entries(logs, n=LATEST_N):
    """Max. één entry per spel: per spel de nieuwste (gelijke datum → de eerste in het bestand), daarna datum aflopend,
    gelijke datum → spelnaam (A→Z); de n bovenste."""
    rows = []
    for cfg, data in logs:
        if not data["entries"]:
            continue
        newest = max(e["date"] for e in data["entries"])
        ent = next(e for e in data["entries"] if e["date"] == newest)
        rows.append((cfg, ent))
    rows.sort(key=lambda r: r[0][1])                     # spelnaam A→Z (stabiele sort: tie-break bij gelijke datum)
    rows.sort(key=lambda r: r[1]["date"], reverse=True)  # datum aflopend
    return rows[:n]


def render_latest(logs, nl, indent):
    e = lambda s: html.escape(s, quote=False)
    a = html.escape
    out = [indent + '<section class="latest" id="latest" aria-labelledby="latest-title">',
           indent + '  <h2 class="section-title" id="latest-title">Latest updates</h2>',
           indent + '  <ol class="latest-list">']
    for cfg, ent in latest_entries(logs):
        gid, name, rel, url, own = cfg
        out += [indent + '    <li><a class="latest-item" href="%s"><span class="latest-meta"><span class="latest-game">%s</span>'
                         '<span class="latest-kind">%s</span><time datetime="%s">%s</time></span><span class="latest-text">%s</span></a></li>'
                % (a(url), render_name(name), e(chief_updates.KIND_LABEL[ent["kind"]]["en"]), a(ent["date"]),
                   e(chief_updates.fmt_date(ent["date"], "en")), e(ent["en"]))]
    out += [indent + "  </ol>", indent + "</section>"]
    return nl.join(out)


def render_updlink(cfg, data, nl, indent):
    """Link "What's new" in de ?-sheet van dice/bingo + updates.js (bolletje op ?), enkel Engels."""
    gid, name, rel, url, own = cfg
    return nl.join([
        indent + '<a id="upd-link" class="chief-upd-link" href="/%s/updates/">What&#39;s new</a>' % own,
        indent + '<script src="../assets/updates/updates.js" data-game="%s" data-latest="%s" defer></script>'
        % (gid, chief_updates.latest(data)),
    ])


def render_updates_page(cfg, data, footer):
    """Volledige statische pagina <own>/updates/index.html (Engels, zoals het spel); footerblok = dat van chief-brand-sync."""
    gid, name, rel, url, own = cfg
    e = lambda s: html.escape(s, quote=False)
    a = html.escape
    ctx = chief_updates.page_context(data, name)
    t = ctx["upd_t"]["en"]
    desc = chief_updates.description(name, data)
    title = "What's new in %s" % name
    icons = "../../assets/icons/%s/" % own
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        '<meta name="theme-color" content="#0a0a0a">',
        "<!-- GENERATED by build.py uit changelog/%s.json (enkel het footerblok komt van chief-brand-sync) -->" % gid,
        '<link rel="icon" href="%sfavicon.ico" sizes="16x16 32x32 48x48">' % icons,
        '<link rel="icon" href="%sfavicon.svg" type="image/svg+xml">' % icons,
        '<link rel="icon" type="image/png" sizes="32x32" href="%sfavicon-32.png">' % icons,
        '<link rel="apple-touch-icon" href="%sapple-touch-icon.png">' % icons,
        "<title>%s</title>" % e(title),
        '<meta name="description" content="%s">' % a(desc),
        '<link rel="canonical" href="%s">' % a(url),
        '<meta property="og:type" content="website">',
        '<meta property="og:url" content="%s">' % a(url),
        '<meta property="og:title" content="%s">' % a(title),
        '<meta property="og:description" content="%s">' % a(desc),
        '<meta property="og:site_name" content="chiefke">',
        '<meta property="og:image" content="https://chiefke.com/assets/og/%s.png">' % own,
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:site" content="@ChiefXBelgium">',
        '<meta name="twitter:title" content="%s">' % a(title),
        '<meta name="twitter:description" content="%s">' % a(desc),
        '<meta name="twitter:image" content="https://chiefke.com/assets/og/%s.png">' % own,
        '<link rel="stylesheet" href="../../assets/brand/chief-tokens.css">',
        '<link rel="stylesheet" href="../../assets/brand/chief-gamebar.css">',
        '<link rel="stylesheet" href="../../assets/brand/chief-footer.css">',
        '<link rel="stylesheet" href="../../assets/updates/updates.css">',
        "<style>",
        "html{color-scheme:dark}",
        "body{margin:0;background:var(--chief-bg);color:var(--chief-text);font-family:var(--chief-font-body);"
        "min-height:100vh;min-height:100dvh;display:flex;flex-direction:column;overflow-x:hidden}",
        ".chief-wordmark span{color:var(--chief-accent)}",
        "</style>",
        '<script src="../../assets/updates/updates.js" data-game="%s" data-latest="%s" data-page="updates" defer></script>'
        % (gid, chief_updates.latest(data)),
        "</head>",
        "<body>",
        '<header class="chief-gamebar">',
        '  <a class="chief-wordmark" href="/%s/">Chief<span>%s</span></a>' % (own, e(name[len(NAME_PREFIX):])),
        '  <div class="chief-gamebar__actions">',
        '    <button id="btn-help" class="chief-gamebar__btn chief-gamebar__btn--help" type="button" aria-label="How to play" '
        'aria-haspopup="dialog" aria-controls="help">?</button>',
        '    <a id="btn-home" class="chief-gamebar__btn chief-gamebar__btn--home" href="/%s/" aria-label="%s">⌂</a>' % (own, a(name)),
        "  </div>",
        "</header>",
        "",
        '<main class="upd">',
        "  <h1>%s</h1>" % e(t["title"]),
        '  <p class="upd-about">%s</p>' % e(t["about"]),
    ]
    for m in ctx["upd_months"]:
        lines += ['  <section class="upd-month" aria-labelledby="m-%s">' % m["key"],
                  '    <h2 id="m-%s">%s</h2>' % (m["key"], e(m["en"])),
                  '    <ol class="upd-list">']
        for ent in m["entries"]:
            lines += ['      <li class="upd-entry">',
                      '        <div class="upd-meta"><time class="upd-date" datetime="%s">%s</time>'
                      '<span class="upd-kind upd-kind--%s">%s</span></div>'
                      % (a(ent["date"]), e(ent["day"]["en"]), ent["kind"], e(ent["label"]["en"])),
                      '        <p class="upd-text">%s</p>' % e(ent["en"]),
                      "      </li>"]
        lines += ["    </ol>", "  </section>"]
    lines += [
        '  <p class="upd-launched">%s</p>' % e(t["launched"]),
        "</main>",
        "",
        '<div id="help" class="chief-sheet" hidden>',
        '  <div class="chief-sheet__box" role="dialog" aria-modal="true" aria-labelledby="help-title">',
        '    <div class="chief-sheet__head"><h2 id="help-title">%s</h2><button id="btn-help-close" class="chief-gamebar__btn" '
        'type="button" aria-label="Close">✕</button></div>' % e(t["title"]),
        '    <p class="upd-sheet-text">%s</p>' % e(t["about"]),
        '    <a class="chief-upd-link" href="/%s/">%s</a>' % (own, e(t["back"])),
        "  </div>",
        "</div>",
        footer,
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(lines)


def updates_page_path(own):
    return os.path.join(HERE, own, "updates", "index.html")


def build_updates_page(cfg, data):
    """→ (pad, oude inhoud of None, nieuwe inhoud); het bestaande footerblok blijft (chief-brand-sync)."""
    path = updates_page_path(cfg[4])
    old = None
    footer = EMPTY_FOOTER
    if os.path.isfile(path):
        with open(path, encoding="utf-8", newline="") as f:
            old = f.read()
        m = FOOTER_RE.search(old)
        if m:
            footer = m.group(0)
    return path, old, render_updates_page(cfg, data, footer)


def write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".partial")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if os.path.exists(path):
        os.chmod(tmp, os.stat(path).st_mode)
    os.replace(tmp, path)


def replace_block(src, name, render, nl):
    pat = re.compile(r"(<!-- %s:START -->)(.*?)(\n?)([ \t]*)(<!-- %s:END -->)" % (name, name), re.S)
    matches = pat.findall(src)
    if len(matches) != 1:
        fail("index.html: expected exactly 1 %s:START/END marker pair, found %d" % (name, len(matches)))
    indent = pat.search(src).group(4)
    return pat.sub(lambda m: m.group(1) + nl + render(nl, indent) + nl + indent + m.group(5), src)


# ---------------------------------------------------------------------- doelmodus (chiefke-app, 2026-11-27)
TARGETS = ("chiefke",)
DEFAULT_URLMAP = os.path.join(HERE, "..", "21_CHIEFKE", "chiefke", "mounts.json")
# niet in de doeluitvoer: repo-/buildbestanden, Pages-config, en wat de chiefke-app zelf serveert (robots, sitemap-index)
TARGET_SKIP_FILES = {"CNAME", "README.md", "build.py", "chief_updates.py", "apps.json", "robots.txt", "sitemap.xml"}
TARGET_SKIP_DIRS = {".git", "__pycache__", "changelog"}
TARGET_TEXT = (".html", ".js", ".css", ".json", ".xml", ".txt", ".webmanifest", ".svg")


def load_urlmap(path):
    """→ (origin, [(oude URL, nieuwe URL)], {oude map: nieuwe map}) uit de mountmap van de chiefke-repo."""
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        origin = cfg["origin"].rstrip("/")
        # [2026-11-27, ronde C] enkel producten met status "live" worden herschreven; "legacy" houdt zijn oude URL
        # (kaarten, Latest updates en JSON-LD wijzen rechtstreeks naar het oude domein tot ronde D)
        for p in cfg["products"]:
            if p.get("status") not in ("legacy", "live"):
                fail("urlmap %s: product %s zonder geldige status (legacy|live)" % (path, p.get("path")))
        pairs = [(p["old"], origin + p["path"]) for p in cfg["products"] if p["status"] == "live"]
        pairs += [(s["old"], origin + s["path"]) for s in cfg["sites"]]
        dirs = {s["dir"]: s["path"].strip("/") for s in cfg["sites"] if s.get("dir") and s.get("site") == "hub"}
    except (OSError, ValueError, KeyError, TypeError) as e:
        fail("urlmap %s: %s" % (path, e))
    for old, new in pairs:
        if not (old.startswith("https://") and old.endswith("/") and new.startswith("https://") and new.endswith("/")):
            fail("urlmap: oude en nieuwe URL moeten https:// zijn en op / eindigen: %s → %s" % (old, new))
    return origin, pairs, dirs


def url_rewriter(pairs, dirs):
    """Eén pass (geen dubbele vervanging): elke oude URL (met én zonder www., ook zonder afsluitende / als het pad
    / is) → nieuwe URL, langste pad eerst; root-paden "/<map>/" van de hub → "/<nieuwe map>/"."""
    alts, target = [], {}
    for old, new in sorted(pairs, key=lambda p: -len(p[0])):
        host, _, path = old[len("https://"):].partition("/")
        host = host[4:] if host.startswith("www.") else host
        key = (host, "/" + path)
        target[key] = new
        rx = r"https://(?:www\.)?%s/%s" % (re.escape(host), re.escape(path))
        if path == "":
            rx += r"|https://(?:www\.)?%s(?![\w./-])" % re.escape(host)
        alts.append((rx, new))
    big = re.compile("|".join("(%s)" % rx for rx, _ in alts))
    news = [n for _, n in alts]
    dir_rx = re.compile(r"""(?<=["'(=])/(%s)(?=[/"'?#])""" % "|".join(re.escape(d) for d in sorted(dirs, key=len, reverse=True))) if dirs else None

    def rewrite(text):
        def sub(m):
            for i, n in enumerate(news):
                if m.group(i + 1) is not None:
                    return n if m.group(i + 1).endswith("/") else n.rstrip("/") + ("/" if n.count("/") > 3 else "")
            return m.group(0)
        out = big.sub(sub, text)
        if dir_rx is not None:
            out = dir_rx.sub(lambda m: "/" + dirs[m.group(1)], out)
        return out
    return rewrite


TAG_RX = re.compile(r"<([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*>")
SEO_LINK_REL = re.compile(r"""\brel\s*=\s*["']?\s*(canonical|alternate)\b""", re.I)


def link_relativizer(origin):
    """[2026-11-27, ronde B] → functie(html) die href/src/action naar <origin>/… pad-relatief maakt (vanaf de root),
    behalve in <link rel="canonical|alternate">. og/twitter (content=), JSON-LD ("url": …) en tekst blijven absoluut."""
    attr_rx = re.compile(r"""(\b(?:href|src|action)\s*=\s*)(["'])%s(/[^"']*)?\2""" % re.escape(origin.rstrip("/")))

    def tag(m):
        t = m.group(0)
        if m.group(1).lower() == "link" and SEO_LINK_REL.search(t):
            return t
        return attr_rx.sub(lambda a: a.group(1) + a.group(2) + (a.group(3) or "/") + a.group(2), t)

    return lambda text: TAG_RX.sub(tag, text)


def target_files(generated, rewrite, dirs, relativize=None):
    """→ {relatief pad in de uitvoer: bytes}: elk bestand van de hub (min TARGET_SKIP_*), gegenereerde inhoud waar
    build.py die maakt, tekstbestanden herschreven, mappen hernoemd; sitemap.xml → sitemap-hub.xml."""
    out = {}
    for base, subdirs, files in os.walk(HERE):
        rel_base = os.path.relpath(base, HERE)
        subdirs[:] = sorted(d for d in subdirs if d not in TARGET_SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.startswith(".") or name.endswith(".partial") or name.endswith(".pyc"):
                continue
            if rel_base == "." and name in TARGET_SKIP_FILES:
                continue
            src = os.path.join(base, name)
            rel = os.path.normpath(os.path.join(rel_base, name))
            parts = rel.split(os.sep)
            if parts[0] in dirs:
                parts[0] = dirs[parts[0]]
            dest = "/".join(parts)
            if src in generated:
                data = generated[src].encode("utf-8")
            else:
                with open(src, "rb") as f:
                    data = f.read()
            if name.endswith(TARGET_TEXT):
                text = rewrite(data.decode("utf-8"))
                if relativize is not None and name.endswith(".html"):
                    text = relativize(text)
                data = text.encode("utf-8")
            out[dest] = data
    sm = os.path.join(HERE, "sitemap.xml")
    if os.path.isfile(sm):
        with open(sm, encoding="utf-8", newline="") as f:
            out["sitemap-hub.xml"] = rewrite(f.read()).encode("utf-8")
    return out


def write_bytes_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".partial")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def build_target(generated, out_dir, urlmap, check, groups_for_target):
    """Doeluitvoer schrijven (of --check). generated = {pad in de hub: nieuwe inhoud} van de doel-generatie."""
    origin, pairs, dirs = load_urlmap(urlmap)
    rewrite = url_rewriter(pairs, dirs)
    files = target_files(generated, rewrite, dirs, link_relativizer(origin))
    out_dir = os.path.abspath(out_dir)
    if out_dir == HERE or out_dir.startswith(HERE + os.sep):
        fail("--out mag niet in de hub-repo liggen (%s)" % out_dir)
    stale, extra = [], []
    for rel, data in sorted(files.items()):
        p = os.path.join(out_dir, *rel.split("/"))
        old = None
        if os.path.isfile(p):
            with open(p, "rb") as f:
                old = f.read()
        if old != data:
            stale.append(rel)
    if os.path.isdir(out_dir):
        for base, subdirs, names in os.walk(out_dir):
            for n in names:
                rel = os.path.relpath(os.path.join(base, n), out_dir).replace(os.sep, "/")
                if rel not in files and not n.endswith(".partial"):
                    extra.append(rel)
    for rel in sorted(extra):
        print("NOTE: %s staat in %s maar hoort niet meer bij de doeluitvoer (niet gewist)" % (rel, out_dir))
    if check:
        if stale:
            for rel in stale:
                print("stale: %s — run build.py --target chiefke --out %s" % (rel, out_dir), file=sys.stderr)
            return 1
        print("doeluitvoer up-to-date: %s (%d bestanden)" % (out_dir, len(files)))
        return 0
    for rel in stale:
        write_bytes_atomic(os.path.join(out_dir, *rel.split("/")), files[rel])
    print("doelbuild chiefke ok: %s (%d bestanden, %d geschreven, origin %s)" % (out_dir, len(files), len(stale), origin))
    return 0


def parse_args(argv):
    a = {"check": False, "target": None, "out": None, "urlmap": DEFAULT_URLMAP}
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == "--check":
            a["check"] = True
        elif x in ("--target", "--out", "--urlmap") and i + 1 < len(argv):
            a[x[2:]] = argv[i + 1]
            i += 1
        else:
            fail("usage: build.py [--check] [--target chiefke --out <map> [--urlmap <mounts.json>]] (onbekend: %s)" % x)
        i += 1
    if a["target"] is not None and (a["target"] not in TARGETS or not a["out"]):
        fail("usage: --target %s vereist --out <map>" % "|".join(TARGETS))
    if a["out"] and a["target"] is None:
        fail("usage: --out enkel samen met --target")
    return a


def main_target(a):
    groups = load_apps()
    origin, pairs, dirs = load_urlmap(a["urlmap"])
    rewrite = url_rewriter(pairs, dirs)
    groups = [(sec, [dict(app, url=rewrite(app["url"])) for app in grp]) for sec, grp in groups]
    apps = flat(groups)
    logs = load_changelogs()
    with open(INDEX, encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"
    out = replace_block(src, "APPS", lambda n, i: render_cards(groups, n, i), nl)
    out = replace_block(out, "JSONLD", lambda n, i: render_jsonld(apps, n, i), nl)
    out = replace_block(out, "META", render_meta, nl)
    out = replace_block(out, "LATEST", lambda n, i: render_latest(logs, n, i), nl)
    generated = {INDEX: out}
    for cfg, data in logs:
        own = cfg[4]
        if own is None:
            continue
        page = os.path.join(HERE, own, "index.html")
        with open(page, encoding="utf-8", newline="") as f:
            psrc = f.read()
        pnl = "\r\n" if "\r\n" in psrc else "\n"
        generated[page] = replace_block(psrc, "UPDLINK", lambda n, i, c=cfg, d=data: render_updlink(c, d, n, i), pnl)
        path, _old, new = build_updates_page(cfg, data)
        generated[path] = new
    return build_target(generated, a["out"], a["urlmap"], a["check"], groups)


def main():
    a = parse_args(sys.argv[1:])
    if a["target"] is not None:
        return main_target(a)
    check = a["check"]
    groups = load_apps()
    apps = flat(groups)
    logs = load_changelogs()
    with open(INDEX, encoding="utf-8", newline="") as f:
        src = f.read()
    nl = "\r\n" if "\r\n" in src else "\n"
    out = replace_block(src, "APPS", lambda n, i: render_cards(groups, n, i), nl)
    out = replace_block(out, "JSONLD", lambda n, i: render_jsonld(apps, n, i), nl)
    out = replace_block(out, "META", render_meta, nl)
    out = replace_block(out, "LATEST", lambda n, i: render_latest(logs, n, i), nl)
    plain = unprefixed(apps)
    if plain:
        print("NOTE: no '%s' prefix, title rendered plain: %s" % (NAME_PREFIX, ", ".join(plain)))
    # (pad, oud, nieuw) voor elk gegenereerd bestand; index.html eerst
    todo = [(INDEX, src, out)]
    for cfg, data in logs:
        own = cfg[4]
        if own is None:
            continue
        page = os.path.join(HERE, own, "index.html")
        with open(page, encoding="utf-8", newline="") as f:
            psrc = f.read()
        pnl = "\r\n" if "\r\n" in psrc else "\n"
        todo.append((page, psrc, replace_block(psrc, "UPDLINK", lambda n, i, c=cfg, d=data: render_updlink(c, d, n, i), pnl)))
        todo.append(build_updates_page(cfg, data))
    stale = [p for p, old, new in todo if old != new]
    if not stale:
        print("index.html up-to-date (%d apps, %d sections, %d changelogs)" % (len(apps), len(groups), len(logs)))
        return 0
    if check:
        for p in stale:
            print("stale: %s — run /usr/bin/python3 build.py" % os.path.relpath(p, HERE), file=sys.stderr)
        return 1
    for p, old, new in todo:
        if old != new:
            write_atomic(p, new)
            print("rebuilt %s" % os.path.relpath(p, HERE))
    print("build ok (%d apps, %d sections, %d changelogs)" % (len(apps), len(groups), len(logs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
