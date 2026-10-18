# Chief's Tools — chiefke.com

Static hub for Chief's web apps. One self-contained `index.html` (inline CSS, no JavaScript), no trackers.

The app cards are plain HTML so crawlers and AI fetchers (which don't run JS) read the real descriptions.

## Add or change an app
1. Edit `apps.json` (`name`, `url`, `tag`, `category` = schema.org applicationCategory, `desc`, `points` = 1–3 short bullets).
2. Run `/usr/bin/python3 build.py` — regenerates the cards between `<!-- APPS:START -->`/`<!-- APPS:END -->` and the JSON-LD between `<!-- JSONLD:START -->`/`<!-- JSONLD:END -->`.
3. Update `<meta name="description">` / `og:description` by hand if the app list changed.

`/usr/bin/python3 build.py --check` exits 1 if `index.html` is stale.

## Deploy
GitHub Pages from `main` / root, custom domain via `CNAME` (`chiefke.com`). Push = deploy.
