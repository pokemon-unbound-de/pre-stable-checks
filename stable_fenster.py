#!/usr/bin/env python3
"""
Stable-Fenster-Tracker
======================
Misst das Stable-Kriterium von Pokemon Unbound DE als reproduzierbare
Zahl statt Bauchgefuehl: **Stable v1.0.0 gilt, wenn 14 Tage lang kein
Pflichtfehler** gemeldet wurde (Release v0.1.6/v0.1.7).

Pflichtfehler (die einzigen Stable-Blocker):
    en_rest        englische Reste
    text_breite    Text laeuft aus dem Fenster
    grammatik      Grammatik/Umlaute
    grafik         Grafikfehler
    absturz        Absturz/Speicherproblem

Datenbasis: `stable_fenster.csv` (manuell gepflegt, ohne
Discord-API-Zugang) — eine Zeile pro Pflichtfehler-Meldung aus
`#beta-bugs`:

    id;datum;typ;status;quelle
    SF-001;2026-10-20;en_rest;gefixt;Beta v0.1.6, Ruhmeshalle
    SF-002;2026-10-28;text_breite;offen;...

- `status`: `offen` (offener Fehler, zahlt gegen das Fenster) |
  `gefixt` (fixiert — zahlt bis zum Fix-Datum, danach nicht) |
  `kein_pflichtfehler` (False Positive, zahlt nie)
- `id`: aufsteigend SF-001, SF-002, ...

Der Tracker rechnet aus:
- **Fenster-Ende** = letztes Datum eines Status-`offen`/`gefixt`
  Pflichtfehlers + 14 Tage
- **Status** = "Fenster laeuft noch" / "Stable-Kriterium erfuellt"
- Aggregate je Fehler-Typ

Nutzung:
    python3 stable_fenster.py --csv stable_fenster.csv --heute 2026-11-04
    python3 stable_fenster.py --csv stable_fenster.csv \
        --add "2026-11-04;grammatik;offen;Beta v0.1.7, Kampfturm"
    (ohne --heute: heutiges Datum; --add erzeugt die CSV, falls fehlt)
"""

import argparse
import csv
import os
import re
import sys
from datetime import date, timedelta

PFLICHTFEHLER_TYPEN = ("en_rest", "text_breite", "grammatik",
                       "grafik", "absturz")
GUELTIGE_STATUS = ("offen", "gefixt", "kein_pflichtfehler")
FENSTER_TAGE = 14
ID_RE = re.compile(r"^SF-\d{3,}$")
DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SPALTEN = ["id", "datum", "typ", "status", "quelle"]


def lade(csv_pfad):
    """CSV laden (leere Datei -> leere Liste)."""
    if not os.path.exists(csv_pfad):
        return []
    with open(csv_pfad, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    return [r for r in rows if any((v or "").strip() for v in r.values())]


def speichern(csv_pfad, zeilen):
    with open(csv_pfad, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(SPALTEN)
        for z in zeilen:
            w.writerow([z.get(s, "") for s in SPALTEN])


def naechste_id(zeilen):
    max_n = 0
    for z in zeilen:
        m = re.match(r"^SF-(\d+)$", (z.get("id") or "").strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"SF-{max_n + 1:03d}"


def validiere(zeile, idx):
    fehler = []
    if not ID_RE.match((zeile.get("id") or "").strip()):
        fehler.append(f"Zeile {idx}: ungültige id (erwartet SF-NNN)")
    if not DATUM_RE.match((zeile.get("datum") or "").strip()):
        fehler.append(f"Zeile {idx}: ungültiges datum (erwartet YYYY-MM-DD)")
    if (zeile.get("typ") or "").strip() not in PFLICHTFEHLER_TYPEN:
        fehler.append(f"Zeile {idx}: typ {zeile.get('typ')!r} nicht in "
                      f"{list(PFLICHTFEHLER_TYPEN)}")
    if (zeile.get("status") or "").strip() not in GUELTIGE_STATUS:
        fehler.append(f"Zeile {idx}: status {zeile.get('status')!r} "
                      f"nicht in {list(GUELTIGE_STATUS)}")
    return fehler


def fenster_berechnen(zeilen, heute):
    """(letzes_datum, fenster_ende, fehler_ohne_fp, typ_counter).

    'Zahlend' sind Pflichtfehler mit status offen/gefixt
    (kein_pflichtfehler zahlt nie).
    """
    zählend = []
    typ_counter = {}
    for z in zeilen:
        typ = (z.get("typ") or "").strip()
        status = (z.get("status") or "").strip()
        if typ in PFLICHTFEHLER_TYPEN:
            typ_counter[typ] = typ_counter.get(typ, 0) + 1
        if status in ("offen", "gefixt"):
            try:
                datum = date.fromisoformat((z.get("datum") or "").strip())
            except ValueError:
                continue
            zählend.append((datum, (z.get("id") or "").strip()))
    if not zählend:
        return None, None, 0, typ_counter
    letztes = max(zählend)
    fenster_ende = letztes[0] + timedelta(days=FENSTER_TAGE)
    return letztes, fenster_ende, len(zählend), typ_counter


def main():
    p = argparse.ArgumentParser(description="Stable-Fenster-Tracker")
    p.add_argument("--csv", default="stable_fenster.csv")
    p.add_argument("--heute", default=None,
                   help="Referenz-Datum YYYY-MM-DD (Default: heute)")
    p.add_argument("--add", default=None,
                   help="neue Zeile anhängen: \"datum;typ;status;quelle\" "
                        "(id wird automatisch vergeben)")
    args = p.parse_args()

    heute = (date.fromisoformat(args.heute) if args.heute
             else date.today())
    zeilen = lade(args.csv)

    if args.add:
        teile = [t.strip() for t in args.add.split(";")]
        if len(teile) != 4:
            print("Fehler: --add erwartet \"datum;typ;status;quelle\"",
                  file=sys.stderr)
            return 1
        datum, typ, status, quelle = teile
        try:
            date.fromisoformat(datum)
        except ValueError:
            print(f"Fehler: ungültiges Datum {datum!r} (YYYY-MM-DD)",
                  file=sys.stderr)
            return 1
        if typ not in PFLICHTFEHLER_TYPEN:
            print(f"Fehler: typ {typ!r} nicht in {list(PFLICHTFEHLER_TYPEN)}",
                  file=sys.stderr)
            return 1
        if status not in GUELTIGE_STATUS:
            print(f"Fehler: status {status!r} nicht in {list(GUELTIGE_STATUS)}",
                  file=sys.stderr)
            return 1
        zeilen.append({"id": naechste_id(zeilen), "datum": datum,
                       "typ": typ, "status": status, "quelle": quelle})
        zeilen.sort(key=lambda z: (z.get("datum", ""), z.get("id", "")))
        speichern(args.csv, zeilen)
        print(f"-> {zeilen[-1]['id']} angefügt, {args.csv} "
              f"({len(zeilen)} Zeilen)", file=sys.stderr)

    fehler = []
    for i, z in enumerate(zeilen, start=2):
        fehler.extend(validiere(z, i))
    if fehler:
        for f in fehler:
            print(f"! {f}", file=sys.stderr)
        return 1

    letztes, fenster_ende, n_zählend, typ_counter = \
        fenster_berechnen(zeilen, heute)

    print("=== STABLE-FENSTER ===", file=sys.stderr)
    print(f"Referenz-Datum: {heute.isoformat()}", file=sys.stderr)
    print(f"Einträge: {len(zeilen)} (davon fester {n_zählend}, "
          f"False-Positives: "
          f"{sum(1 for z in zeilen if z.get('status') == 'kein_pflichtfehler')})",
          file=sys.stderr)
    print("Aggregate je Typ:", file=sys.stderr)
    for typ in PFLICHTFEHLER_TYPEN:
        print(f"  {typ}: {typ_counter.get(typ, 0)}", file=sys.stderr)
    if letztes is None:
        print("Status: KEIN Pflichtfehler erfasst — Fenster läuft "
              "(Stable-Kriterium erfüllt, sofern kein nicht erfasster "
              "Fehler vorliegt)", file=sys.stderr)
        return 0
    if heute < fenster_ende:
        rest = (fenster_ende - heute).days
        print(f"Status: FENSTER LÄUFT NOCH — letzter Pflichtfehler "
              f"{letztes[1]} am {letztes[0].isoformat()} + "
              f"{FENSTER_TAGE} Tage = {fenster_ende.isoformat()} "
              f"(noch {rest} Tage)", file=sys.stderr)
        return 0
    if heute == fenster_ende:
        print(f"Status: 14-Tage-Fenster endet HEUTE "
              f"({fenster_ende.isoformat()}) — morgen Stable-fähig",
              file=sys.stderr)
        return 0
    print(f"Status: STABLE-KRITERIUM ERFÜLLT seit {fenster_ende.isoformat()} "
          f"(14 Tage ohne Pflichtfehler nach {letztes[1]} am "
          f"{letztes[0].isoformat()})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
