# Chief's Tools — chiefke.com

Static hub for Chief's web apps. One self-contained `index.html` (inline CSS, no JavaScript), no trackers.

The app cards are plain HTML so crawlers and AI fetchers (which don't run JS) read the real descriptions.

## Add or change an app
1. Edit `apps.json` (`name`, `short` = 2–4 word label for the meta description, `url`, `tag`, `category` = schema.org applicationCategory, `desc`, `points` = 1–3 short bullets). All fields required.
2. Run `/usr/bin/python3 build.py` — regenerates the cards (`<!-- APPS:START/END -->`), the JSON-LD (`<!-- JSONLD:START/END -->`) and `<meta name="description">` + `og:description` (`<!-- META:START/END -->`: "Free, no-signup tools by @ChiefXBelgium: " + `<name> (<short>)` per app).

`/usr/bin/python3 build.py --check` exits 1 if `index.html` is stale; exit 2 = invalid `apps.json` or missing markers. Footer has no year to bump ("Since 2026").

## Deploy
GitHub Pages from `main` / root, custom domain via `CNAME` (`chiefke.com`). Push = deploy.
