/* CHIEF'S QOTD archive — renders each quote client-side in the QOTD template.
   Layout is a port of 13_QOTD's qotd_render_engine.py (autofit 40–130 px on a 1080x1350 canvas, balanced line
   breaks, ink-box centring), so cards and PNG downloads break lines the same way as the real images.
   Data: data/qotd.json = [{date, quote}], newest first. Socials: socials.json ("TODO" = hidden). */
(function () {
  "use strict";

  // ---- template constants (reference canvas 1080x1350, = the 4:5 QOTD image) ----
  var W = 1080, H = 1350;
  var X0 = 140, X1 = 940, MAX_W = X1 - X0, CX = (X0 + X1) / 2, CY = H / 2 - 30, MAX_H = Math.round(H * 0.6);
  var SIZE_MIN = 40, SIZE_MAX = 130, LINE_SPACING = 1.3, BALANCE_MIN = 0.4, SOLO_MIN_LETTERS = 10;
  var BORDER_INSET = 48, BORDER_W = 2, BORDER = "#3a3a3a", TEXT = "#edeae4", SIG = "#8a8680";
  var SIG_TEXT = "CHIEF'S QOTD", SIG_SIZE = 22, SIG_TRACKING = 0.35, SIG_BASELINE = H - 110;
  var FAMILY = '"QOTD Bodoni", "Didot", "Bodoni 72", Georgia, serif';
  var YT = "https://www.youtube.com/@ChiefsQOTD";

  var all = [], view = [], current = -1, layoutCache = {};
  var $ = function (id) { return document.getElementById(id); };
  var grid = $("grid"), lb = $("lb");
  var mctx = document.createElement("canvas").getContext("2d");

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

  function wrap(words) {
    var lines = [], cur = "";
    words.forEach(function (w) {
      var t = cur ? cur + " " + w : w;
      if (!cur || ink(t).w <= MAX_W) cur = t; else { lines.push(cur); cur = w; }
    });
    if (cur) lines.push(cur);
    return lines;
  }
  function fits(words, size) {
    setFont(mctx, size);
    for (var i = 0; i < words.length; i++) if (ink(words[i]).w > MAX_W) return null;
    var lines = wrap(words);
    return blockHeight(lines.length, size) > MAX_H ? null : lines;
  }

  // all splits of words into exactly n lines (each <= MAX_W); no single-word line at 4+ words unless >= 10 letters
  function candidates(words, n) {
    var k = words.length, cache = {}, out = [];
    function lw(i, j) { var key = i + ":" + j; if (!(key in cache)) cache[key] = ink(words.slice(i, j).join(" ")).w; return cache[key]; }
    function ok(i, j) { return j - i >= 2 || k < 4 || letters(words[i]) >= SOLO_MIN_LETTERS; }
    function rec(i, m, cuts) {
      if (m === 1) { if (ok(i, k) && lw(i, k) <= MAX_W) out.push(cuts.concat([k])); return; }
      for (var j = i + 1; j <= k - m + 1; j++) {
        if (lw(i, j) > MAX_W) break;
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
  function bestBalanced(words, size) {
    setFont(mctx, size);
    var nMin = wrap(words).length;
    if (nMin === 1) return [words.join(" ")];
    for (var n = nMin; n <= nMin + 1; n++) {
      if (blockHeight(n, size) > MAX_H || n > words.length) break;
      var best = null;
      candidates(words, n).forEach(function (c) {
        var longest = Math.max.apply(null, c.widths);
        if (c.widths[0] < BALANCE_MIN * longest || c.widths[c.widths.length - 1] < BALANCE_MIN * longest) return;
        var v = variance(c.widths);
        if (!best || v < best.v) best = { v: v, lines: c.lines };
      });
      if (best) return best.lines;
    }
    return null;
  }
  function minmax(words, n) {
    var best = null;
    candidates(words, n).forEach(function (c) {
      var key = [Math.round(Math.max.apply(null, c.widths) * 10), variance(c.widths)];
      if (!best || key[0] < best.k[0] || (key[0] === best.k[0] && key[1] < best.k[1])) best = { k: key, lines: c.lines };
    });
    return best ? best.lines : null;
  }

  // → {size, lines:[{text,x,y}]} in 1080x1350 coordinates
  function layout(raw) {
    if (layoutCache[raw]) return layoutCache[raw];
    var words = quoted(raw).split(/\s+/), lo = SIZE_MIN, hi = SIZE_MAX, fit = null, size, lines = null;
    while (lo <= hi) { size = (lo + hi) >> 1; if (fits(words, size)) { fit = size; lo = size + 1; } else hi = size - 1; }
    if (fit === null) { size = SIZE_MIN; setFont(mctx, size); lines = wrap(words); }
    else {
      for (size = fit; size >= SIZE_MIN; size--) { lines = bestBalanced(words, size); if (lines) break; }
      if (!lines) { size = fit; setFont(mctx, size); var g = wrap(words); lines = minmax(words, g.length) || g; }
    }
    setFont(mctx, size);
    var step = size * LINE_SPACING, boxes = lines.map(function (t) { return ink(t); });
    var top = Math.min.apply(null, boxes.map(function (b, i) { return i * step - b.asc; }));
    var bottom = Math.max.apply(null, boxes.map(function (b, i) { return i * step + b.desc; }));
    var y0 = CY - (bottom - top) / 2 - top;
    var out = { size: size, lines: lines.map(function (t, i) {
      var b = boxes[i];
      return { text: t, x: CX - (b.r - b.l) / 2 - b.l, y: y0 + i * step };
    }) };
    layoutCache[raw] = out;
    return out;
  }

  // ---- SVG card ----
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function cardSVG(raw) {
    var L = layout(raw), track = SIG_SIZE * SIG_TRACKING;
    var tspans = L.lines.map(function (l) { return '<tspan x="' + l.x.toFixed(1) + '" y="' + l.y.toFixed(1) + '">' + esc(l.text) + "</tspan>"; }).join("");
    return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(quoted(raw)) + '">' +
      '<rect x="' + (BORDER_INSET + BORDER_W / 2) + '" y="' + (BORDER_INSET + BORDER_W / 2) + '" width="' + (W - 2 * BORDER_INSET - BORDER_W) +
      '" height="' + (H - 2 * BORDER_INSET - BORDER_W) + '" fill="none" stroke="' + BORDER + '" stroke-width="' + BORDER_W + '"/>' +
      '<text font-family=\'' + FAMILY + '\' font-weight="700" font-size="' + L.size + '" fill="' + TEXT + '">' + tspans + "</text>" +
      '<text x="' + (W / 2 + track / 2) + '" y="' + SIG_BASELINE + '" text-anchor="middle" font-family=\'' + FAMILY +
      '\' font-weight="400" font-size="' + SIG_SIZE + '" letter-spacing="' + track + '" fill="' + SIG + '">' + esc(SIG_TEXT) + "</text></svg>";
  }

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
    grid.textContent = "";
    var frag = document.createDocumentFragment();
    view.forEach(function (e, i) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button"; b.className = "item"; b.id = "q-" + e.date;
      b.setAttribute("aria-label", "Open quote of " + e.date);
      b.addEventListener("click", function () { open(i); });
      var card = document.createElement("span");
      card.className = "qcard"; card.dataset.quote = e.quote;
      card.innerHTML = '<span class="ph"></span>';
      var t = document.createElement("time");
      t.dateTime = e.date; t.textContent = fmtDate(e.date);
      b.appendChild(card); b.appendChild(t); li.appendChild(b); frag.appendChild(li);
      if (io) io.observe(card); else renderCard(card);
    });
    grid.appendChild(frag);
    $("count").textContent = view.length === all.length ? all.length + (all.length === 1 ? " quote" : " quotes")
      : view.length + " of " + all.length + " quotes";
    $("empty").hidden = view.length > 0;
  }

  function filter() {
    var q = norm($("q").value.trim());
    view = q ? all.filter(function (e) { return norm(e.quote).indexOf(q) !== -1; }) : all.slice();
    draw();
  }

  // ---- lightbox ----
  function open(i) {
    if (i < 0 || i >= view.length) return;
    current = i;
    var e = view[i];
    var card = $("lb-card");
    card.innerHTML = cardSVG(e.quote);
    $("lb-date").textContent = fmtDate(e.date);
    $("lb-prev").disabled = i === 0;
    $("lb-next").disabled = i === view.length - 1;
    $("lb-copy").querySelector("span").textContent = "Copy link";
    if (location.hash !== "#" + e.date) history.replaceState(null, "", "#" + e.date);
    if (!lb.open) { lb.showModal(); document.body.classList.add("lb-open"); }
  }
  function close() {
    if (lb.open) lb.close();
  }
  lb.addEventListener("close", function () {
    document.body.classList.remove("lb-open");
    if (location.hash) history.replaceState(null, "", location.pathname + location.search);
    var e = view[current];
    if (e) { var b = $("q-" + e.date); if (b) b.focus({ preventScroll: true }); }
  });
  $("lb-close").addEventListener("click", close);
  $("lb-prev").addEventListener("click", function () { open(current - 1); });
  $("lb-next").addEventListener("click", function () { open(current + 1); });
  lb.addEventListener("click", function (ev) { if (ev.target === lb || ev.target.classList.contains("lb-inner")) close(); });
  document.addEventListener("keydown", function (ev) {
    if (!lb.open) return;
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

  $("lb-copy").addEventListener("click", function () {
    var e = view[current]; if (!e) return;
    var url = location.origin + location.pathname + "#" + e.date, label = this.querySelector("span");
    function done(ok) { label.textContent = ok ? "Copied" : url; }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(false); });
    else done(false);
  });

  // ---- PNG download (1080x1350, the real QOTD 4:5 size) ----
  function grain(ctx) {
    var img = ctx.getImageData(0, 0, W, H), d = img.data;
    for (var i = 0; i < d.length; i += 4) {
      var n = (Math.random() + Math.random() - 1) * 6;   // triangular ±6, like the engine's grain
      d[i] += n; d[i + 1] += n; d[i + 2] += n;
    }
    ctx.putImageData(img, 0, 0);
  }
  function png(e) {
    document.fonts.ready.then(function () {
      var c = document.createElement("canvas"); c.width = W; c.height = H;
      var ctx = c.getContext("2d");
      ctx.fillStyle = "#0f0f0f"; ctx.fillRect(0, 0, W, H);
      var g = ctx.createRadialGradient(W / 2, -H * 0.05, 0, W / 2, -H * 0.05, H * 0.75);
      g.addColorStop(0, "rgba(255,255,255,0.04)"); g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(1, H / W);
      var v = ctx.createRadialGradient(0, 0, W * 0.25, 0, 0, W * 0.72);
      v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,0.6)");
      ctx.fillStyle = v; ctx.fillRect(-W, -W, 2 * W, 2 * W); ctx.restore();
      grain(ctx);
      ctx.strokeStyle = BORDER; ctx.lineWidth = BORDER_W;
      ctx.strokeRect(BORDER_INSET + BORDER_W / 2, BORDER_INSET + BORDER_W / 2, W - 2 * BORDER_INSET - BORDER_W, H - 2 * BORDER_INSET - BORDER_W);
      var L = layout(e.quote);
      setFont(ctx, L.size); ctx.fillStyle = TEXT; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
      L.lines.forEach(function (l) { ctx.fillText(l.text, l.x, l.y); });
      setFont(ctx, SIG_SIZE, 400); ctx.fillStyle = SIG;
      var track = SIG_SIZE * SIG_TRACKING, chars = SIG_TEXT.split(""), widths = chars.map(function (ch) { return ctx.measureText(ch).width; });
      var total = widths.reduce(function (a, b) { return a + b; }, 0) + track * (chars.length - 1), x = (W - total) / 2;
      chars.forEach(function (ch, i) { ctx.fillText(ch, x, SIG_BASELINE); x += widths[i] + track; });
      c.toBlob(function (blob) {
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "chiefs-qotd-" + e.date + ".png";
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      }, "image/png");
    });
  }
  $("lb-png").addEventListener("click", function () { var e = view[current]; if (e) png(e); });

  // ---- random + deep link ----
  $("random").addEventListener("click", function () {
    if (!view.length) return;
    var i = Math.floor(Math.random() * view.length);
    if (view.length > 1 && i === current) i = (i + 1) % view.length;
    open(i);
  });
  function fromHash() {
    var m = /^#(\d{4}-\d{2}-\d{2})$/.exec(location.hash);
    if (!m) { if (lb.open) close(); return; }
    var i = view.findIndex(function (e) { return e.date === m[1]; });
    if (i === -1) {   // deep link outside the current search → clear the search first
      $("q").value = ""; view = all.slice(); draw();
      i = view.findIndex(function (e) { return e.date === m[1]; });
    }
    if (i !== -1) open(i);
  }
  window.addEventListener("hashchange", fromHash);

  // ---- socials ----
  var ICONS = {
    youtube: '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="M10 9l5 3-5 3z"/>',
    x: '<path d="M5 5l14 14M19 5L5 19"/>',
    tiktok: '<path d="M9 18a3 3 0 1 1 0-6M9 18a3 3 0 0 0 3-3V4c1 2.5 3 4 6 4"/>',
    instagram: '<rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3.5"/><circle cx="17" cy="7" r=".6"/>',
    kofi: '<path d="M4 9h12v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM16 10h1.5a2.5 2.5 0 0 1 0 5H16M8 4v2M12 4v2"/>'
  };
  var LABELS = { youtube: "YouTube", x: "X", tiktok: "TikTok", instagram: "Instagram", kofi: "Ko-fi" };
  function socials(cfg) {
    var yt = cfg.youtube && cfg.youtube !== "TODO" ? cfg.youtube : YT;
    Array.prototype.forEach.call(document.querySelectorAll('[data-social="youtube"]'), function (a) { a.href = yt; });
    var ul = $("socials");
    ["youtube", "x", "tiktok", "instagram", "kofi"].forEach(function (k) {
      var url = cfg[k];
      if (!url || url === "TODO" || !/^https:\/\//.test(url)) return;
      var li = document.createElement("li"), a = document.createElement("a");
      a.href = url; a.target = "_blank"; a.rel = "noopener";
      a.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24">' + ICONS[k] + "</svg>" + LABELS[k];
      li.appendChild(a); ul.appendChild(li);
    });
  }

  // ---- boot ----
  fetch("socials.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(socials, function () { socials({}); });

  var fontsReady = Promise.all([
    document.fonts.load('700 100px "QOTD Bodoni"'),
    document.fonts.load('400 22px "QOTD Bodoni"')
  ]).catch(function () {}).then(function () { return document.fonts.ready; });

  Promise.all([fetch("data/qotd.json", { cache: "no-cache" }).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }), fontsReady]).then(function (res) {
    all = (res[0] || []).filter(function (e) { return e && /^\d{4}-\d{2}-\d{2}$/.test(e.date) && typeof e.quote === "string"; });
    view = all.slice();
    draw();
    fromHash();
  }).catch(function () {
    $("count").textContent = "Couldn't load the archive. Try again later.";
  });

  var t;
  $("q").addEventListener("input", function () { clearTimeout(t); t = setTimeout(filter, 120); });
})();
