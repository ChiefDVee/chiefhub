# Chief's Tools — chiefke.com

Static hub for Chief's web apps. One self-contained `index.html` (inline CSS/JS), no build step, no trackers.

## Add an app
Add one line to the `APPS` array in `index.html`:

```js
{ name: "ChiefX", url: "https://chiefx.com", desc: "One sentence.", tag: "Bitcoin" },
```

## Deploy
GitHub Pages from `main` / root, custom domain via `CNAME` (`chiefke.com`). Push = deploy.
