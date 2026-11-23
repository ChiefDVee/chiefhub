/* CHIEF'S QOTD archive — renders each quote client-side in the QOTD template.
   Layout is a port of 13_QOTD's qotd_render_engine.py (autofit 40–130 px, balanced line breaks, ink-box centring),
   per format: Post = the 4:5 image (1080x1350, FMT_45), Story = the 9:16 image (1080x1920, FMT_916).
   One layout() feeds both the on-screen SVG cards and the PNG canvas, so screen and download never drift apart.
   Data: data/qotd.json = [{date, quote}], newest first. Favorites: localStorage "chief_qotd_favs" (array of dates).
   No trackers, no external requests: the Share menu targets are plain links, only opened on click. */
(function () {
  "use strict";

  // ---- template formats (coordinates = the real QOTD images) ----
  var FMT = {
    post:  { key: "post",  w: 1080, h: 1350, x0: 140, x1: 940, cy: 1350 / 2 - 30, maxH: 810, sig: 1240, label: "Post 1080×1350" },
    story: { key: "story", w: 1080, h: 1920, x0: 140, x1: 900, cy: 875,           maxH: 860, sig: 1420, label: "Story 1080×1920" }
  };
  var SIZE_MIN = 40, SIZE_MAX = 130, LINE_SPACING = 1.3, BALANCE_MIN = 0.4, SOLO_MIN_LETTERS = 10;
  var BORDER_INSET = 48, BORDER_W = 2, BORDER = "#3a3a3a", TEXT = "#edeae4", SIG = "#8a8680";
  var SIG_TEXT = "CHIEF'S QOTD", SIG_SIZE = 22, SIG_TRACKING = 0.35;
  var URL_TEXT = "chiefke.com/qotd", URL_SIZE = 17, URL_TRACKING = 0.2, URL_GAP = 36;
  var FAMILY = '"QOTD Bodoni", "Didot", "Bodoni 72", Georgia, serif';
  var BASE = "https://chiefke.com/qotd/";
  var FAV_KEY = "chief_qotd_favs", DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

  var all = [], view = [], current = -1, layoutCache = {}, blobCache = {}, blobOrder = [];
  var favs = null, favOnly = false, refilterOnClose = false;
  var $ = function (id) { return document.getElementById(id); };
  var grid = $("grid"), lb = $("lb"), live = $("status");
  var mctx = document.createElement("canvas").getContext("2d");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- text helpers ----
  function curl(text) {   // same rule as curl_single(): ' at word start → ‘, every other ' → ’
    return text.replace(/(^|[\s"“‘(\[{])'/g, "$1‘").replace(/'/g, "’");
  }
  function quoted(text) { return "“" + curl(text) + "”"; }
  function norm(s) { return s.toLowerCase().replace(/[‘’]/g, "'").replace(/[“”]/g, '"'); }
  function letters(w) { return w.replace(/[^A-Za-z]/g, "").length; }
  function fmtDate(iso) {
    var d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long", year: "numeric" });
  }
  function permalink(e) { return BASE + "?d=" + e.date; }
  function copyText(e) { return quoted(e.quote) + " — Chief's QOTD"; }
  // Post = chiefs-qotd-YYYY-MM-DD.png; Story gets a suffix, otherwise it overwrites the Post in the same folder
  function fileName(e, f) { return "chiefs-qotd-" + e.date + (f && f.key === "story" ? "-story" : "") + ".png"; }

  // ---- measuring (ink box, like the engine's ink_width) ----
  function setFont(ctx, size, weight) { ctx.font = (weight || 700) + " " + size + "px " + FAMILY; }
  function ink(text) {
    var m = mctx.measureText(text);
    var l = -m.actualBoundingBoxLeft, r = m.actualBoundingBoxRight;
    return { l: l, r: r, w: Math.max(r, m.width) - Math.min(l, 0), asc: m.actualBoundingBoxAscent, desc: m.actualBoundingBoxDescent };
  }
  function metrics(size) {
    var m = mctx.measureText("Hg");
    var a = m.fontBoundingBoxAscent, d = m.fontBoundingBoxDescent;
    if (!(a > 0)) { a = size * 0.92; d = size * 0.24; }
    return { asc: a, desc: d };
  }
  function blockHeight(n, size) { var m = metrics(size); return (n - 1) * size * LINE_SPACING + m.asc + m.desc; }

  function wrap(words, maxW) {
    var lines = [], cur = "";
    words.forEach(function (w) {
      var t = cur ? cur + " " + w : w;
      if (!cur || ink(t).w <= maxW) cur = t; else { lines.push(cur); cur = w; }
    });
    if (cur) lines.push(cur);
    return lines;
  }
  function fits(words, size, f) {
    var maxW = f.x1 - f.x0;
    setFont(mctx, size);
    for (var i = 0; i < words.length; i++) if (ink(words[i]).w > maxW) return null;
    var lines = wrap(words, maxW);
    return blockHeight(lines.length, size) > f.maxH ? null : lines;
  }

  // all splits of words into exactly n lines (each <= maxW); no single-word line at 4+ words unless >= 10 letters
  function candidates(words, n, maxW) {
    var k = words.length, cache = {}, out = [];
    function lw(i, j) { var key = i + ":" + j; if (!(key in cache)) cache[key] = ink(words.slice(i, j).join(" ")).w; return cache[key]; }
    function ok(i, j) { return j - i >= 2 || k < 4 || letters(words[i]) >= SOLO_MIN_LETTERS; }
    function rec(i, m, cuts) {
      if (m === 1) { if (ok(i, k) && lw(i, k) <= maxW) out.push(cuts.concat([k])); return; }
      for (var j = i + 1; j <= k - m + 1; j++) {
        if (lw(i, j) > maxW) break;
        if (!ok(i, j)) continue;
        rec(j, m - 1, cuts.concat([j]));
      }
    }
    rec(0, n, []);
    return out.map(function (cuts) {
      var b = [0].concat(cuts), widths = [], lines = [];
      for (var x = 0; x < cuts.length; x++) { widths.push(lw(b[x], b[x + 1])); lines.push(words.slice(b[x], b[x + 1]).join(" ")); }
      return { widths: widths, lines: lines };
    });
  }
  function variance(ws) { var m = ws.reduce(function (a, b) { return a + b; }, 0) / ws.length; return ws.reduce(function (a, w) { return a + (w - m) * (w - m); }, 0) / ws.length; }
  function bestBalanced(words, size, f) {
    var maxW = f.x1 - f.x0;
    setFont(mctx, size);
    var nMin = wrap(words, maxW).length;
    if (nMin === 1) return [words.join(" ")];
    for (var n = nMin; n <= nMin + 1; n++) {
      if (blockHeight(n, size) > f.maxH || n > words.length) break;
      var best = null;
      candidates(words, n, maxW).forEach(function (c) {
        var longest = Math.max.apply(null, c.widths);
        if (c.widths[0] < BALANCE_MIN * longest || c.widths[c.widths.length - 1] < BALANCE_MIN * longest) return;
        var v = variance(c.widths);
        if (!best || v < best.v) best = { v: v, lines: c.lines };
      });
      if (best) return best.lines;
    }
    return null;
  }
  function minmax(words, n, maxW) {
    var best = null;
    candidates(words, n, maxW).forEach(function (c) {
      var key = [Math.round(Math.max.apply(null, c.widths) * 10), variance(c.widths)];
      if (!best || key[0] < best.k[0] || (key[0] === best.k[0] && key[1] < best.k[1])) best = { k: key, lines: c.lines };
    });
    return best ? best.lines : null;
  }

  // → {size, lines:[{text,x,y}]} in the coordinates of format f (default: Post)
  function layout(raw, f) {
    f = f || FMT.post;
    var ck = f.key + "|" + raw;
    if (layoutCache[ck]) return layoutCache[ck];
    var maxW = f.x1 - f.x0, cx = (f.x0 + f.x1) / 2;
    var words = quoted(raw).split(/\s+/), lo = SIZE_MIN, hi = SIZE_MAX, fit = null, size, lines = null;
    while (lo <= hi) { size = (lo + hi) >> 1; if (fits(words, size, f)) { fit = size; lo = size + 1; } else hi = size - 1; }
    if (fit === null) { size = SIZE_MIN; setFont(mctx, size); lines = wrap(words, maxW); }
    else {
      for (size = fit; size >= SIZE_MIN; size--) { lines = bestBalanced(words, size, f); if (lines) break; }
      if (!lines) { size = fit; setFont(mctx, size); var g = wrap(words, maxW); lines = minmax(words, g.length, maxW) || g; }
    }
    setFont(mctx, size);
    var step = size * LINE_SPACING, boxes = lines.map(function (t) { return ink(t); });
    var top = Math.min.apply(null, boxes.map(function (b, i) { return i * step - b.asc; }));
    var bottom = Math.max.apply(null, boxes.map(function (b, i) { return i * step + b.desc; }));
    var y0 = f.cy - (bottom - top) / 2 - top;
    var out = { size: size, lines: lines.map(function (t, i) {
      var b = boxes[i];
      return { text: t, x: cx - (b.r - b.l) / 2 - b.l, y: y0 + i * step };
    }) };
    layoutCache[ck] = out;
    return out;
  }

  // ---- SVG card (screen, Post format) ----
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function cardSVG(raw) {
    var f = FMT.post, W = f.w, H = f.h, L = layout(raw, f), track = SIG_SIZE * SIG_TRACKING;
    var tspans = L.lines.map(function (l) { return '<tspan x="' + l.x.toFixed(1) + '" y="' + l.y.toFixed(1) + '">' + esc(l.text) + "</tspan>"; }).join("");
    return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(quoted(raw)) + '">' +
      '<rect x="' + (BORDER_INSET + BORDER_W / 2) + '" y="' + (BORDER_INSET + BORDER_W / 2) + '" width="' + (W - 2 * BORDER_INSET - BORDER_W) +
      '" height="' + (H - 2 * BORDER_INSET - BORDER_W) + '" fill="none" stroke="' + BORDER + '" stroke-width="' + BORDER_W + '"/>' +
      '<text font-family=\'' + FAMILY + '\' font-weight="700" font-size="' + L.size + '" fill="' + TEXT + '">' + tspans + "</text>" +
      '<text x="' + (W / 2 + track / 2) + '" y="' + f.sig + '" text-anchor="middle" font-family=\'' + FAMILY +
      '\' font-weight="400" font-size="' + SIG_SIZE + '" letter-spacing="' + track + '" fill="' + SIG + '">' + esc(SIG_TEXT) + "</text></svg>";
  }

  // ---- PNG render (canvas, Post or Story) ----
  function grain(ctx, W, H) {
    var img = ctx.getImageData(0, 0, W, H), d = img.data;
    for (var i = 0; i < d.length; i += 4) {
      var n = (Math.random() + Math.random() - 1) * 6;   // triangular ±6, like the engine's grain
      d[i] += n; d[i + 1] += n; d[i + 2] += n;
    }
    ctx.putImageData(img, 0, 0);
  }
  function tracked(ctx, text, size, weight, tracking, baseline, W) {
    setFont(ctx, size, weight);
    var track = size * tracking, chars = text.split(""), widths = chars.map(function (ch) { return ctx.measureText(ch).width; });
    var total = widths.reduce(function (a, b) { return a + b; }, 0) + track * (chars.length - 1), x = (W - total) / 2;
    chars.forEach(function (ch, i) { ctx.fillText(ch, x, baseline); x += widths[i] + track; });
  }
  function drawPNG(e, f) {
    var W = f.w, H = f.h, c = document.createElement("canvas"); c.width = W; c.height = H;
    var ctx = c.getContext("2d");
    ctx.fillStyle = "#0f0f0f"; ctx.fillRect(0, 0, W, H);
    var g = ctx.createRadialGradient(W / 2, -H * 0.05, 0, W / 2, -H * 0.05, H * 0.75);
    g.addColorStop(0, "rgba(255,255,255,0.04)"); g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(1, H / W);
    var v = ctx.createRadialGradient(0, 0, W * 0.25, 0, 0, W * 0.72);
    v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,0.6)");
    ctx.fillStyle = v; ctx.fillRect(-W, -W, 2 * W, 2 * W); ctx.restore();
    grain(ctx, W, H);
    ctx.strokeStyle = BORDER; ctx.lineWidth = BORDER_W;
    ctx.strokeRect(BORDER_INSET + BORDER_W / 2, BORDER_INSET + BORDER_W / 2, W - 2 * BORDER_INSET - BORDER_W, H - 2 * BORDER_INSET - BORDER_W);
    var L = layout(e.quote, f);
    setFont(ctx, L.size); ctx.fillStyle = TEXT; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
    L.lines.forEach(function (l) { ctx.fillText(l.text, l.x, l.y); });
    ctx.fillStyle = SIG;
    tracked(ctx, SIG_TEXT, SIG_SIZE, 400, SIG_TRACKING, f.sig, W);
    tracked(ctx, URL_TEXT, URL_SIZE, 400, URL_TRACKING, f.sig + URL_GAP, W);
    return c;
  }
  function renderPNG(e, f) {   // → Promise<Blob>; cached per format + date (small LRU)
    var key = f.key + "|" + e.date;
    if (blobCache[key]) return blobCache[key];
    var p = fontsReady.then(function () { return document.fonts.ready; }).then(function () {
      var c = drawPNG(e, f);
      return new Promise(function (res, rej) { c.toBlob(function (b) { if (b) res(b); else rej(new Error("toBlob")); }, "image/png"); });
    });
    blobCache[key] = p; blobOrder.push(key);
    while (blobOrder.length > 6) delete blobCache[blobOrder.shift()];
    p.catch(function () { delete blobCache[key]; });
    return p;
  }
  function download(e, f) {
    return renderPNG(e, f).then(function (blob) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fileName(e, f);
      (lb.open ? lb : document.body).appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
    });
  }

  // ---- clipboard ----
  function legacyCopy(text) {
    var ta = document.createElement("textarea"), ok = false;
    ta.value = text; ta.setAttribute("readonly", "");
    ta.style.position = "fixed"; ta.style.top = "-1000px"; ta.style.opacity = "0";
    (lb.open ? lb : document.body).appendChild(ta);
    ta.select(); ta.setSelectionRange(0, text.length);
    try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
    ta.remove();
    return ok;
  }
  function copy(text) {
    return new Promise(function (res, rej) {
      function fallback() { if (legacyCopy(text)) res(); else rej(new Error("copy")); }
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(res, fallback);
      else fallback();
    });
  }
  function flash(btn, msg) {
    btn.setAttribute("data-flash", msg);
    clearTimeout(btn._flashT);
    btn._flashT = setTimeout(function () { btn.removeAttribute("data-flash"); }, 1600);
    if (live) { live.textContent = ""; setTimeout(function () { live.textContent = msg; }, 30); }
  }

  // ---- favorites (localStorage; any failure silently disables the feature) ----
  function loadFavs() {
    try {
      var probe = "__chief_qotd_probe";
      localStorage.setItem(probe, "1"); localStorage.removeItem(probe);
      var raw = localStorage.getItem(FAV_KEY), arr = [];
      try { arr = raw ? JSON.parse(raw) : []; } catch (_) { arr = []; }
      favs = {};
      if (Array.isArray(arr)) arr.forEach(function (d) { if (typeof d === "string" && DATE_RE.test(d)) favs[d] = 1; });
    } catch (_) { favs = null; }
    if (!favs) document.body.classList.add("no-favs");
  }
  function disableFavs() {
    favs = null;
    document.body.classList.add("no-favs");
    if (favOnly) { favOnly = false; $("favs").setAttribute("aria-pressed", "false"); filter(); }
  }
  function isFav(date) { return !!(favs && favs[date]); }
  function favCount() { return favs ? Object.keys(favs).length : 0; }
  function toggleFav(e) {
    if (!favs) return;
    var on = !favs[e.date];
    if (on) favs[e.date] = 1; else delete favs[e.date];
    try { localStorage.setItem(FAV_KEY, JSON.stringify(Object.keys(favs).sort().reverse())); }
    catch (_) { disableFavs(); return; }
    Array.prototype.forEach.call(document.querySelectorAll('[data-fav="' + e.date + '"]'), function (b) { setFavBtn(b, e.date); });
    if (live) live.textContent = on ? "Added to favorites" : "Removed from favorites";
    if (favOnly) { if (lb.open) refilterOnClose = true; else filter(); }
  }
  function setFavBtn(b, date) {
    var on = isFav(date);
    b.setAttribute("aria-pressed", on ? "true" : "false");
    b.setAttribute("aria-label", (on ? "Remove from favorites: " : "Add to favorites: ") + "quote of " + date);
    b.title = on ? "Unfavorite" : "Favorite";
  }

  // ---- per-quote action row ----
  var ICON = {
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    download: '<path d="M12 4v11M7 10l5 5 5-5M5 19h14"/>',
    share: '<path d="M12 15V4M8 8l4-4 4 4M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    fav: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20z"/>',
    // share targets: monochrome line icons (currentColor), no brand colours
    whatsapp: '<path d="M20 11.5a8 8 0 0 1-11.8 7L4 20l1.4-4A8 8 0 1 1 20 11.5z"/><path d="M9.2 8.8c0 3 2.9 5.9 5.9 5.9l.9-1.6-1.9-.9-.8.8a4.4 4.4 0 0 1-2.4-2.4l.8-.8-.9-1.9z"/>',
    x: '<path d="M5 4h3.6L19 20h-3.6zM18.6 4l-5.8 6.6M11.2 13.4L5.4 20"/>',
    facebook: '<path d="M14 21v-8h2.8l.5-3.3H14V7.9c0-1 .4-1.7 1.8-1.7h1.6V3.3A20 20 0 0 0 15 3.1c-2.5 0-4.2 1.5-4.2 4.3v2.3H8V13h2.8v8"/>',
    telegram: '<path d="M21 4L3 11.2l6.2 2.3M21 4l-3 16-6.6-5.1M21 4L9.2 13.5V19l2.2-4.6"/>',
    bluesky: '<path d="M12 10.8C10.2 7.3 6.9 4.8 5 4.8c-1.4 0-1.7 1.3-1.4 3.1.4 2.2 2 3.4 4.9 3.2-2.9.6-3.6 2.5-2.1 4.2 2.6 2.8 4.2-.3 5.6-3.4 1.4 3.1 3 6.2 5.6 3.4 1.5-1.7.8-3.6-2.1-4.2 2.9.2 4.5-1 4.9-3.2.3-1.8 0-3.1-1.4-3.1-1.9 0-5.2 2.5-7 6z"/>',
    reddit: '<ellipse cx="12" cy="14.5" rx="8" ry="5.5"/><path d="M12 9l1.4-5 4.6 1.3"/><circle cx="19.2" cy="5.6" r="1.4"/><path d="M9 16.6c1.8 1.1 4.2 1.1 6 0M9 13h.01M15 13h.01"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.6 6.6L12 13l8.4-6.4"/>',
    more: '<circle cx="5.5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18.5" cy="12" r="1.2"/>'
  };
  function svgIcon(kind) { return '<svg aria-hidden="true" viewBox="0 0 24 24">' + ICON[kind] + "</svg>"; }
  // direct share targets (order = menu order); text = “quote” — Chief's QOTD, url = ?d= permalink
  function shareTargets(e) {
    var t = copyText(e), u = permalink(e), enc = encodeURIComponent;
    return [
      { key: "whatsapp", label: "WhatsApp", url: "https://wa.me/?text=" + enc(t + " " + u) },
      { key: "x",        label: "X",        url: "https://x.com/intent/post?text=" + enc(t) + "&url=" + enc(u) + "&via=ChiefXBelgium" },
      { key: "facebook", label: "Facebook", url: "https://www.facebook.com/sharer/sharer.php?u=" + enc(u) },
      { key: "telegram", label: "Telegram", url: "https://t.me/share/url?url=" + enc(u) + "&text=" + enc(t) },
      { key: "bluesky",  label: "Bluesky",  url: "https://bsky.app/intent/compose?text=" + enc(t + " " + u) },
      { key: "reddit",   label: "Reddit",   url: "https://www.reddit.com/submit?url=" + enc(u) + "&title=" + enc(t) },
      { key: "mail",     label: "Email",    url: "mailto:?subject=" + enc("Chief's QOTD") + "&body=" + enc(t + "\n\n" + u), same: true }
    ];
  }
  // phone with file sharing → "Share image…" goes first (route to Instagram/TikTok/WhatsApp with the picture)
  var fileShare = null;
  function canShareFiles() {
    if (fileShare !== null) return fileShare;
    fileShare = false;
    try {
      fileShare = !!(navigator.share && navigator.canShare &&
        navigator.canShare({ files: [new File([""], "chiefs-qotd.png", { type: "image/png" })] }));
    } catch (_) { fileShare = false; }
    return fileShare;
  }
  function imageFirst() {
    return canShareFiles() && !!(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
  }
  function mkBtn(kind, label, aria, withLabel) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "qa-btn qa-" + kind;
    b.setAttribute("aria-label", aria); b.title = label;
    b.innerHTML = svgIcon(kind) + (withLabel ? "<span>" + label + "</span>" : "");
    return b;
  }
  var openMenu = null;
  function closeMenu(focusBack) {
    if (!openMenu) return;
    var m = openMenu; openMenu = null;
    m.menu.hidden = true; m.btn.setAttribute("aria-expanded", "false");
    if (focusBack) m.btn.focus();
  }
  function toggleMenu(menu, btn, ev) {   // one menu open at a time; focus into the menu on open
    ev.stopPropagation();
    if (openMenu && openMenu.menu === menu) { closeMenu(false); return; }
    closeMenu(false);
    menu.hidden = false; btn.setAttribute("aria-expanded", "true");
    openMenu = { menu: menu, btn: btn };
    var first = menu.querySelector("button, a");
    if (first) first.focus({ preventScroll: true });
    // whole menu into view (a card low on the screen would otherwise hide the last targets below the fold)
    if (menu.scrollIntoView) menu.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
  }
  function shareMenu(e, bShare) {
    var menu = document.createElement("div");
    menu.className = "qa-menu qa-sharemenu"; menu.hidden = true;
    menu.setAttribute("aria-label", "Share quote of " + e.date);
    var list = document.createElement("div");
    list.className = "qa-targets";
    shareTargets(e).forEach(function (t) {
      var a = document.createElement("a");
      a.className = "qa-size qa-target qa-t-" + t.key; a.href = t.url;
      a.setAttribute("aria-label", t.same ? "Email quote of " + e.date : "Share quote of " + e.date + " on " + t.label);
      if (!t.same) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
      a.innerHTML = svgIcon(t.key) + "<span>" + t.label + "</span>";
      a.addEventListener("click", function (ev) {
        if (!t.same) { ev.preventDefault(); window.open(t.url, "_blank", "noopener,noreferrer"); }
        closeMenu(true);   // mailto: default navigation in the same tab
      });
      list.appendChild(a);
    });
    var bCopyLink = document.createElement("button");
    bCopyLink.type = "button"; bCopyLink.className = "qa-size qa-target qa-t-link";
    bCopyLink.setAttribute("aria-label", "Copy link to quote of " + e.date);
    bCopyLink.innerHTML = svgIcon("link") + "<span>Copy link</span>";
    bCopyLink.addEventListener("click", function () { closeMenu(true); copyLink(e, bShare); });
    list.appendChild(bCopyLink);
    if (navigator.share) {
      var first = imageFirst();
      var bMore = document.createElement("button");
      bMore.type = "button"; bMore.className = "qa-size qa-target qa-t-more";
      bMore.setAttribute("aria-label", (first ? "Share image of quote of " : "More share options for quote of ") + e.date);
      bMore.innerHTML = svgIcon(first ? "share" : "more") + "<span>" + (first ? "Share image…" : "More…") + "</span>";
      bMore.addEventListener("click", function () { closeMenu(true); share(e, bShare); });
      if (first) list.insertBefore(bMore, list.firstChild); else list.appendChild(bMore);
    }
    menu.appendChild(list);
    var hint = document.createElement("p");
    hint.className = "qa-hint";
    hint.textContent = "Instagram/TikTok: download the image and post it from the app.";
    menu.appendChild(hint);
    return menu;
  }
  function actions(e, withLabels) {
    var row = document.createElement("div");
    row.className = "qa" + (withLabels ? " qa-wide" : "");
    var d = e.date;

    var bCopy = mkBtn("copy", "Copy", "Copy quote of " + d, withLabels);
    bCopy.addEventListener("click", function () {
      copy(copyText(e)).then(function () { flash(bCopy, "Copied"); }, function () { flash(bCopy, "Copy failed"); });
    });

    var bDl = mkBtn("download", "Download", "Download image of quote of " + d, withLabels);
    bDl.setAttribute("aria-haspopup", "true"); bDl.setAttribute("aria-expanded", "false");
    var menu = document.createElement("div");
    menu.className = "qa-menu"; menu.hidden = true;
    menu.setAttribute("aria-label", "Image size");
    ["post", "story"].forEach(function (k) {
      var it = document.createElement("button");
      it.type = "button"; it.className = "qa-size"; it.textContent = FMT[k].label;
      it.addEventListener("click", function () {
        closeMenu(true);
        download(e, FMT[k]).then(function () { flash(bDl, "Saved"); }, function () { flash(bDl, "Download failed"); });
      });
      menu.appendChild(it);
    });
    bDl.addEventListener("click", function (ev) { toggleMenu(menu, bDl, ev); });

    var bShare = mkBtn("share", "Share", "Share quote of " + d, withLabels);
    bShare.setAttribute("aria-haspopup", "true"); bShare.setAttribute("aria-expanded", "false");
    var sMenu = shareMenu(e, bShare);
    function warm() { if (navigator.share) renderPNG(e, FMT.post).catch(function () {}); }   // PNG ready before More…
    bShare.addEventListener("pointerdown", warm);
    bShare.addEventListener("focus", warm);
    bShare.addEventListener("click", function (ev) { toggleMenu(sMenu, bShare, ev); });

    var bLink = mkBtn("link", "Link", "Copy link to quote of " + d, withLabels);
    bLink.addEventListener("click", function () { copyLink(e, bLink); });

    var bFav = mkBtn("fav", "Favorite", "", withLabels);
    bFav.setAttribute("data-fav", d);
    setFavBtn(bFav, d);
    bFav.addEventListener("click", function () { toggleFav(e); });

    [bCopy, bDl, bShare, bLink, bFav].forEach(function (b) { row.appendChild(b); });
    row.appendChild(menu);
    row.appendChild(sMenu);
    return row;
  }
  function copyLink(e, btn) {
    copy(permalink(e)).then(function () { flash(btn, "Link copied"); }, function () { flash(btn, "Copy failed"); });
  }
  function share(e, btn) {
    if (!navigator.share) { copyLink(e, btn); return; }
    var text = copyText(e), url = permalink(e);
    renderPNG(e, FMT.post).then(function (blob) {
      var file = null;
      try { file = new File([blob], fileName(e), { type: "image/png" }); } catch (_) { file = null; }
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        return navigator.share({ files: [file], title: "Chief's QOTD", text: text + " " + url });
      }
      return navigator.share({ title: "Chief's QOTD", text: text, url: url });
    }, function () {
      return navigator.share({ title: "Chief's QOTD", text: text, url: url });
    }).catch(function (err) {
      if (err && err.name === "AbortError") return;   // user closed the share sheet
      copyLink(e, btn);
    });
  }
  document.addEventListener("click", function (ev) {
    if (openMenu && !openMenu.menu.contains(ev.target) && ev.target !== openMenu.btn) closeMenu(false);
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && openMenu) { ev.preventDefault(); ev.stopPropagation(); closeMenu(true); }
  }, true);

  // ---- grid with lazy render ----
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      renderCard(e.target);
      io.unobserve(e.target);
    });
  }, { rootMargin: "300px 0px" }) : null;

  function renderCard(el) {
    if (el.dataset.done) return;
    el.innerHTML = cardSVG(el.dataset.quote);
    el.dataset.done = "1";
  }

  function draw() {
    if (io) io.disconnect();
    closeMenu(false);
    grid.textContent = "";
    var frag = document.createDocumentFragment();
    view.forEach(function (e, i) {
      var li = document.createElement("li");
      li.setAttribute("data-date", e.date);
      var b = document.createElement("button");
      b.type = "button"; b.className = "item"; b.id = "q-" + e.date;
      b.setAttribute("aria-label", "Open quote of " + e.date);
      b.addEventListener("click", function () { open(i); });
      var card = document.createElement("span");
      card.className = "qcard"; card.dataset.quote = e.quote;
      card.innerHTML = '<span class="ph"></span>';
      var t = document.createElement("time");
      t.dateTime = e.date; t.textContent = fmtDate(e.date);
      b.appendChild(card); b.appendChild(t); li.appendChild(b);
      li.appendChild(actions(e, false));
      frag.appendChild(li);
      if (io) io.observe(card); else renderCard(card);
    });
    grid.appendChild(frag);
    var n = view.length, s = function (k, one, many) { return k + (k === 1 ? one : many); };
    $("count").textContent = favOnly ? (n === favCount() ? s(n, " favorite", " favorites") : n + " of " + s(favCount(), " favorite", " favorites"))
      : n === all.length ? s(all.length, " quote", " quotes") : n + " of " + all.length + " quotes";
    var empty = $("empty");
    empty.textContent = favOnly && !favCount() ? "No favorites yet. Tap the ♥ on a quote to keep it here." : "Nothing matches. Even the void has standards.";
    empty.hidden = n > 0;
  }

  function filter() {
    var q = norm($("q").value.trim());
    view = all.filter(function (e) {
      return (!favOnly || isFav(e.date)) && (!q || norm(e.quote).indexOf(q) !== -1);
    });
    draw();
  }

  $("favs").addEventListener("click", function () {
    if (!favs) return;
    favOnly = !favOnly;
    this.setAttribute("aria-pressed", favOnly ? "true" : "false");
    filter();
  });

  // ---- lightbox ----
  function open(i) {
    if (i < 0 || i >= view.length) return;
    closeMenu(false);
    current = i;
    var e = view[i];
    $("lb-card").innerHTML = cardSVG(e.quote);
    $("lb-date").textContent = fmtDate(e.date);
    $("lb-prev").disabled = i === 0;
    $("lb-next").disabled = i === view.length - 1;
    var slot = $("lb-actions");
    slot.textContent = "";
    slot.appendChild(actions(e, true));
    if (location.hash !== "#" + e.date) history.replaceState(null, "", "#" + e.date);
    if (!lb.open) { lb.showModal(); document.body.classList.add("lb-open"); }
  }
  function close() {
    if (lb.open) lb.close();
  }
  lb.addEventListener("close", function () {
    closeMenu(false);
    document.body.classList.remove("lb-open");
    if (location.hash) history.replaceState(null, "", location.pathname + location.search);
    var e = view[current];
    if (refilterOnClose) { refilterOnClose = false; filter(); }
    if (e) { var b = $("q-" + e.date); if (b) b.focus({ preventScroll: true }); }
  });
  $("lb-close").addEventListener("click", close);
  $("lb-prev").addEventListener("click", function () { open(current - 1); });
  $("lb-next").addEventListener("click", function () { open(current + 1); });
  lb.addEventListener("click", function (ev) { if (ev.target === lb || ev.target.classList.contains("lb-inner")) close(); });
  document.addEventListener("keydown", function (ev) {
    if (!lb.open || openMenu) return;
    if (ev.target && ev.target.tagName === "INPUT") return;
    if (ev.key === "ArrowLeft") { ev.preventDefault(); open(current - 1); }
    else if (ev.key === "ArrowRight") { ev.preventDefault(); open(current + 1); }
  });
  (function swipe() {
    var x0 = null, y0 = null, card = $("lb-card");
    card.addEventListener("pointerdown", function (e) { x0 = e.clientX; y0 = e.clientY; });
    card.addEventListener("pointerup", function (e) {
      if (x0 === null) return;
      var dx = e.clientX - x0, dy = e.clientY - y0;
      x0 = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) open(current + (dx < 0 ? 1 : -1));
    });
    card.addEventListener("pointercancel", function () { x0 = null; });
  })();

  // ---- random + deep links ----
  $("random").addEventListener("click", function () {
    if (!view.length) return;
    var i = Math.floor(Math.random() * view.length);
    if (view.length > 1 && i === current) i = (i + 1) % view.length;
    open(i);
  });
  function resetFilters() {
    $("q").value = "";
    if (favOnly) { favOnly = false; $("favs").setAttribute("aria-pressed", "false"); }
    view = all.slice(); draw();
  }
  function fromHash() {   // #YYYY-MM-DD → open the lightbox (older shared links)
    var m = /^#(\d{4}-\d{2}-\d{2})$/.exec(location.hash);
    if (!m) { if (lb.open) close(); return; }
    var i = view.findIndex(function (e) { return e.date === m[1]; });
    if (i === -1 && all.some(function (e) { return e.date === m[1]; })) {   // outside the current filter → clear it first
      resetFilters();
      i = view.findIndex(function (e) { return e.date === m[1]; });
    }
    if (i !== -1) open(i);
  }
  function fromQuery() {   // ?d=YYYY-MM-DD → scroll to that quote and highlight it; unknown date = ignored
    var d = null;
    try { d = new URLSearchParams(location.search).get("d"); } catch (_) { d = null; }
    if (!d || !DATE_RE.test(d) || !all.some(function (e) { return e.date === d; })) return;
    var li = grid.querySelector('li[data-date="' + d + '"]');
    if (!li) return;
    renderCard(li.querySelector(".qcard"));
    li.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
    li.classList.add("hl");
    setTimeout(function () { li.classList.remove("hl"); }, 2600);
  }
  window.addEventListener("hashchange", fromHash);

  // ---- boot ----
  loadFavs();
  var fontsReady = Promise.all([
    document.fonts.load('700 100px "QOTD Bodoni"'),
    document.fonts.load('400 22px "QOTD Bodoni"')
  ]).catch(function () {}).then(function () { return document.fonts.ready; });

  Promise.all([fetch("data/qotd.json", { cache: "no-cache" }).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }), fontsReady]).then(function (res) {
    all = (res[0] || []).filter(function (e) { return e && DATE_RE.test(e.date) && typeof e.quote === "string"; });
    view = all.slice();
    draw();
    fromQuery();
    fromHash();
  }).catch(function () {
    $("count").textContent = "Couldn't load the archive. Try again later.";
  });

  var t;
  $("q").addEventListener("input", function () { clearTimeout(t); t = setTimeout(filter, 120); });
})();
