/* updates.js — "What's new" per spel (2026-11-26, updates ronde 2). Kopie per repo (zelfde inhoud).
   Laden via asset_url, met data-attributen op de eigen script-tag:
     src=".../updates.js?v=..." data-game="pairs" data-latest="2026-11-26" [data-page="updates"] [data-i18n="ShuffleI18n"] defer
   - Bolletje: de server zet data-latest = datum van de nieuwste changelog-entry. Is die later dan de laatst bekeken datum
     (localStorage "chief-updates-seen:<game>", in try/catch; niets bewaard = nog nooit bekeken), dan krijgen de ?-knop
     (.chief-gamebar__btn--help) en de link in de ?-sheet (.chief-upd-link) de klasse .chief-upd-new (bolletje, updates.css).
     Ook bij pageshow (terug uit de bfcache na een bezoek aan de updates-pagina).
   - Updates-pagina (data-page="updates"): bij het laden data-latest als bekeken bewaren (bolletje weg), taal via de
     bestaande i18n van de site (window[data-i18n]: lang() + setLang(), regels ?lang= > localStorage > en): <html lang>
     + aria-pressed op de EN|NL-toggle; beide talen staan in de server-HTML, updates.css toont enkel [data-l=<taal>].
     Zonder data-i18n (Engels-only sites) blijft <html lang="en">. De ?-sheet (#help) openen/sluiten: ✕, Escape, tik
     buiten de box; focus terug op ?.
   Geen innerHTML, geen externe requests. window.ChiefUpdates = {isNew, paint, seen} voor de headless-check. */
(function () {
  "use strict";
  var me = document.currentScript || {};
  var data = me.dataset || {};
  var GAME = data.game || "";
  var LATEST = data.latest || "";
  var PAGE = data.page === "updates";
  var I = data.i18n ? window[data.i18n] : null;
  var KEY = "chief-updates-seen:" + GAME;
  var DATE = /^\d{4}-\d{2}-\d{2}$/;

  function seen() {
    var v = "";
    try { v = window.localStorage.getItem(KEY) || ""; } catch (e) { v = ""; }
    return DATE.test(v) ? v : "";
  }
  function markSeen() {
    if (!DATE.test(LATEST)) { return; }
    try { window.localStorage.setItem(KEY, LATEST); } catch (e) { /* privémodus: bolletje blijft */ }
  }
  function isNew() { return DATE.test(LATEST) && LATEST > seen(); }   // ISO-datums: tekstvergelijking = datumvergelijking

  function paint() {
    var on = !PAGE && isNew();
    var list = document.querySelectorAll(".chief-gamebar__btn--help, .chief-upd-link");
    for (var i = 0; i < list.length; i++) {
      if (on) { list[i].classList.add("chief-upd-new"); } else { list[i].classList.remove("chief-upd-new"); }
    }
  }

  function $(id) { return document.getElementById(id); }

  function applyLang() {
    if (!I || typeof I.lang !== "function") { return; }
    var l = I.lang() === "nl" ? "nl" : "en";
    document.documentElement.lang = l;
    var btns = document.querySelectorAll(".chief-lang [data-lang]");
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute("aria-pressed", btns[i].getAttribute("data-lang") === l ? "true" : "false");
    }
  }

  function placeHelp() {
    var h = document.querySelector("header.chief-gamebar");
    document.body.style.setProperty("--chief-gamebar-h", (h ? Math.max(0, Math.ceil(h.getBoundingClientRect().bottom)) : 0) + "px");
  }
  function openHelp() {
    var sheet = $("help");
    if (!sheet) { return; }
    placeHelp();
    sheet.hidden = false;
    sheet.scrollTop = 0;
    var x = $("btn-help-close");
    if (x) { try { x.focus({ preventScroll: true }); } catch (e) { x.focus(); } }
  }
  function closeHelp() {
    var sheet = $("help");
    if (!sheet || sheet.hidden) { return; }
    sheet.hidden = true;
    var b = $("btn-help");
    if (b) { try { b.focus({ preventScroll: true }); } catch (e) { b.focus(); } }
  }

  function initPage() {
    markSeen();
    applyLang();
    document.addEventListener("click", function (ev) {
      var t = ev.target;
      var lang = t && t.closest ? t.closest(".chief-lang [data-lang]") : null;
      if (lang && I && typeof I.setLang === "function") {
        I.setLang(lang.getAttribute("data-lang"));
        applyLang();
        return;
      }
      if (t && t.closest && t.closest("#btn-help")) {
        if ($("help") && $("help").hidden) { openHelp(); } else { closeHelp(); }
        return;
      }
      if (t && t.closest && t.closest("#btn-help-close")) { closeHelp(); return; }
      if (t && t.id === "help") { closeHelp(); }
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { closeHelp(); }
    });
    window.addEventListener("resize", function () { if ($("help") && !$("help").hidden) { placeHelp(); } });
  }

  if (PAGE) { initPage(); }
  paint();
  window.addEventListener("pageshow", paint);
  window.addEventListener("storage", function (ev) { if (!ev || ev.key === KEY) { paint(); } });
  window.ChiefUpdates = { isNew: isNew, paint: paint, seen: seen, key: KEY };
})();
