#!/usr/bin/python3
# ============================================================
# Script Name : chief_updates.py
# Author      : Devriendt Chief
# Datum       : 2026-11-26
# Last Run    : $(date +'%Y-%m-%d %H:%M:%S')
#
# NOTICE: Internal System Chiefbase/Chiefmobile.
# APOCALYPSE WARNING: Apocalypse alert if misconfigured.
# © Devriendt Chief – Private Internal Tool
# ============================================================
"""chief_updates.py — changelog per spel + "What's new"-pagina (2026-11-26, updates ronde 2).

Eén JSON-bestand per spel (bv. app/changelog/<spel>.json), schema:
  {"game": "<id>", "launched": "YYYY-MM-DD",
   "entries": [{"date": "YYYY-MM-DD", "kind": "new|improved|fixed", "en": "…", "nl": "…"}]}
Regels (validate): exact die sleutels; nieuwste eerst (datums dalend, gelijk mag), niet vóór launched; beide talen
ingevuld, ≤ MAX_TEXT tekens, geen code-termen (pad, .py/.js, api, seq, token, commit-hash …) en geen persoonsnamen of
rollen; de oudste entry = de launch (datum = launched, kind new, "… launched." / "… gelanceerd.").
load(path, game) valideert bij het opstarten (create_app): een fout changelog = RuntimeError, nooit stil een lege pagina.
page_context(data, name) → alles wat de template nodig heeft (beide talen, per maand gegroepeerd). Tekst gaat in de
template altijd via Jinja-autoescape, in JS via textContent.
Kopie per repo (zelfde inhoud, zoals chief_feedback.py); de hub (14_CHIEFHUB/build.py) leest dezelfde JSON's lokaal.
"""
import datetime
import json
import re

KINDS = ("new", "improved", "fixed")
KIND_LABEL = {"new": {"en": "New", "nl": "Nieuw"},
              "improved": {"en": "Improved", "nl": "Beter"},
              "fixed": {"en": "Fixed", "nl": "Opgelost"}}
LANGS = ("en", "nl")
MAX_TEXT = 160
KEYS = {"game", "launched", "entries"}
ENTRY_KEYS = {"date", "kind", "en", "nl"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
# spelerstaal: geen paden, bestandsnamen, code- of infratermen, geen commit-hashes (hex met cijfer én letter, ≥ 7)
CODE_TERMS = re.compile(r"/|\\|`|[{}<>_=]|\.(?:py|js|css|html|json|md|txt|sqlite)\b|\b(?:api|seq|token|json|css|html|sql|"
                        r"sqlite|endpoint|refactor|commit|deploy|cache|localstorage|pythonanywhere|flask|regex|"
                        r"familiecode|family code)\b|\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b", re.I)
# geen namen van personen of rollen (ook niet de maker of de familie)
PERSON_TERMS = re.compile(r"\b(?:Chief|partner|papa|mama|oma|opa|vriendin|vriend|zoon|dochter|wife|husband|son|daughter)\b",
                          re.I)
MONTHS = {"en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                 "November", "December"),
          "nl": ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
                 "november", "december")}
MONTHS_SHORT = {"en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
                "nl": ("jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec")}
LAUNCH_SUFFIX = {"en": "launched.", "nl": "gelanceerd."}
TEXTS = {"en": {"title": "What's new in {name}", "launched": "Launched on {date}", "back": "Play {name}",
                "about": "Everything players notice in {name}, newest first.", "link": "What's new"},
         "nl": {"title": "Nieuw in {name}", "launched": "Gelanceerd op {date}", "back": "Speel {name}",
                "about": "Alles wat je als speler merkt in {name}, nieuwste eerst.", "link": "Wat is er nieuw"}}


class ChangelogError(RuntimeError):
    """Changelog ontbreekt of voldoet niet aan het schema."""


def parse_date(value):
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        return datetime.date(int(value[:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        return None


def text_errors(text, where):
    """Fouten in één spelerszin (lege lijst = ok)."""
    out = []
    if not isinstance(text, str) or not text.strip():
        return ["%s: leeg" % where]
    if text != text.strip() or "\n" in text:
        out.append("%s: witruimte aan de rand of een regeleinde" % where)
    if len(text) > MAX_TEXT:
        out.append("%s: %d tekens (max %d)" % (where, len(text), MAX_TEXT))
    m = CODE_TERMS.search(text)
    if m:
        out.append("%s: code-term %r" % (where, m.group(0)))
    m = PERSON_TERMS.search(text)
    if m:
        out.append("%s: persoonsnaam of rol %r" % (where, m.group(0)))
    return out


def validate(data, game=None):
    """→ lijst met fouten (leeg = geldig). game = verwachte id (None = niet controleren)."""
    if not isinstance(data, dict):
        return ["changelog is geen object"]
    errs = []
    if set(data) != KEYS:
        errs.append("sleutels %s (verwacht %s)" % (sorted(data), sorted(KEYS)))
    gid = data.get("game")
    if not isinstance(gid, str) or not GAME_RE.match(gid):
        errs.append("game %r ongeldig" % (gid,))
    elif game is not None and gid != game:
        errs.append("game %r (verwacht %r)" % (gid, game))
    launched = parse_date(data.get("launched"))
    if launched is None:
        errs.append("launched %r is geen YYYY-MM-DD" % (data.get("launched"),))
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return errs + ["entries: lege of geen lijst"]
    prev = None
    for i, e in enumerate(entries):
        where = "entries[%d]" % i
        if not isinstance(e, dict):
            errs.append("%s: geen object" % where)
            continue
        if set(e) != ENTRY_KEYS:
            errs.append("%s: sleutels %s (verwacht %s)" % (where, sorted(e), sorted(ENTRY_KEYS)))
        d = parse_date(e.get("date"))
        if d is None:
            errs.append("%s: date %r is geen YYYY-MM-DD" % (where, e.get("date")))
        else:
            if launched is not None and d < launched:
                errs.append("%s: %s ligt vóór launched %s" % (where, d, launched))
            if prev is not None and d > prev:
                errs.append("%s: %s is nieuwer dan de entry erboven (%s): nieuwste eerst" % (where, d, prev))
            prev = d
        if e.get("kind") not in KINDS:
            errs.append("%s: kind %r (verwacht %s)" % (where, e.get("kind"), "|".join(KINDS)))
        for lang in LANGS:
            errs.extend(text_errors(e.get(lang), "%s.%s" % (where, lang)))
    last = entries[-1]
    if isinstance(last, dict):
        if launched is not None and parse_date(last.get("date")) != launched:
            errs.append("oudste entry: datum %r ≠ launched %s" % (last.get("date"), launched))
        if last.get("kind") != "new":
            errs.append("oudste entry: kind %r (de launch is new)" % (last.get("kind"),))
        for lang in LANGS:
            if not (isinstance(last.get(lang), str) and last[lang].endswith(LAUNCH_SUFFIX[lang])):
                errs.append("oudste entry.%s eindigt niet op %r" % (lang, LAUNCH_SUFFIX[lang]))
        if sum(1 for e in entries if isinstance(e, dict) and isinstance(e.get("en"), str)
               and e["en"].endswith(LAUNCH_SUFFIX["en"])) != 1:
            errs.append("precies één launch-entry verwacht")
    return errs


def load(path, game=None):
    """JSON lezen + valideren; fout → ChangelogError met alle fouten (luid falen bij het opstarten)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ChangelogError("changelog %s onleesbaar: %s" % (path, exc)) from None
    errs = validate(data, game)
    if errs:
        raise ChangelogError("changelog %s ongeldig:\n  " % path + "\n  ".join(errs))
    return data


def latest(data):
    return data["entries"][0]["date"]


def fmt_date(value, lang):
    d = parse_date(value)
    return "%d %s %d" % (d.day, MONTHS[lang][d.month - 1], d.year)


def short_date(value, lang):
    d = parse_date(value)
    return "%d %s" % (d.day, MONTHS_SHORT[lang][d.month - 1])


def months(data):
    """Entries per maand (nieuwste eerst), elk met de datum en het soortlabel in beide talen."""
    groups = []
    for e in data["entries"]:
        d = parse_date(e["date"])
        key = "%04d-%02d" % (d.year, d.month)
        if not groups or groups[-1]["key"] != key:
            groups.append({"key": key, "en": "%s %d" % (MONTHS["en"][d.month - 1], d.year),
                           "nl": "%s %d" % (MONTHS["nl"][d.month - 1], d.year), "entries": []})
        groups[-1]["entries"].append({"date": e["date"], "kind": e["kind"], "en": e["en"], "nl": e["nl"],
                                      "day": {lang: short_date(e["date"], lang) for lang in LANGS},
                                      "label": KIND_LABEL[e["kind"]]})
    return groups


def text(key, lang, **kw):
    return TEXTS[lang][key].format(**kw)


def description(name, data):
    """Engelse meta description (≤ 155 tekens)."""
    out = "What's new in %s: every change players notice since the launch on %s, newest first." % (
        name, fmt_date(data["launched"], "en"))
    return out if len(out) <= 155 else out[:152].rstrip() + "…"


def page_context(data, name):
    """Template-context voor de updates-pagina van één spel (beide talen in de server-HTML)."""
    return {"upd_name": name, "upd_game": data["game"], "upd_latest": latest(data), "upd_months": months(data),
            "upd_kinds": KIND_LABEL,
            "upd_t": {lang: {k: text(k, lang, name=name, date=fmt_date(data["launched"], lang)) for k in TEXTS[lang]}
                      for lang in LANGS}}


def link_context(data, name, url):
    """Context voor de "What's new"-link in de ?-sheet van het spel + het bolletje (data-attribuut met de nieuwste datum)."""
    return {"upd_url": url, "upd_game": data["game"], "upd_latest": latest(data),
            "upd_link": {lang: TEXTS[lang]["link"] for lang in LANGS}, "upd_name": name}
