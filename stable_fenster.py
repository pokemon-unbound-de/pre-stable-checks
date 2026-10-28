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

    id;datum;fix_datum;typ;status;quelle
    SF-001;2026-10-20;2026-10-21;en_rest;gefixt;Beta v0.1.6, Ruhmeshalle
    SF-002;2026-10-28;;text_breite;offen;Beta v0.1.7, Kampfturm

- `datum`: Meldedatum (YYYY-MM-DD)
- `fix_datum`: Fixdatum (YYYY-MM-DD) — **Pflicht bei `gefixt`**,
  leer bei `offen`/`kein_pflichtfehler`. Das 14-Tage-Fenster laeuft
  vom **Fixdatum**, nicht vom Meldedatum. Muss >= `datum` sein.
- `status`:
    `offen`             offener Fehler — blockiert das Stable-Kriterium
                        VOLLSTAENDIG (unabhaengig von Fenstern, wird
                        niemals gruen); muess in `gefixt` (mit
                        fix_datum) oder `kein_pflichtfehler` geaendert
                        werden
    `gefixt`            fixiert — Fenster laeuft ab fix_datum
    `kein_pflichtfehler` False Positive, zahlt nie
- `id`: aufsteigend SF-001, SF-002, ...

Aussagefaehigkeit: Eine fehlende, leere oder nur aus
`kein_pflichtfehler`-Zeilen bestehende CSV bedeutet **UNBESTAETIGT** —
es liegen keine Daten vor, die das Kriterium bestaetigen. Der Tracker
gibt in diesem Fall **keine Freigabe** aus.

Exit-Codes (maschinenlesbar; 0 = gruen, alles andere = kein Freigabe):
    0 = STABLE-KRITERIUM ERFÜLLT
    1 = Input-Fehler (fehlende/ungültige Daten, Schema-Mismatch)
    2 = NICHT GRÜN (offener Pflichtfehler / Fenster läuft /
        Fenster endet heute / UNBESTAETIGT)

Nutzung:
    python3 stable_fenster.py --csv stable_fenster.csv --heute 2026-11-04
    python3 stable_fenster.py --csv stable_fenster.csv \
        --add "2026-11-04;;grammatik;offen;Beta v0.1.7, Kampfturm"
    python3 stable_fenster.py --csv stable_fenster.csv \
        --add "2026-11-04;2026-11-06;grammatik;gefixt;Beta v0.1.7, Kampfturm"
    (--add erwartet "datum;fix_datum;typ;status;quelle"; fix_datum leer
     bei offen/kein_pflichtfehler, Pflicht bei gefixt)
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

SPALTEN = ["id", "datum", "fix_datum", "typ", "status", "quelle"]
ALTSPALTEN = ["id", "datum", "typ", "status", "quelle"]


def _datum_parse(s):
    """Datum parsen (None bei ungültigem Wert)."""
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def lade(csv_pfad):
    """CSV laden.

    Gibt `(zeilen, fehler)` zurück: `fehler` ist None oder eine
    Meldung (Schema-Mismatch). Fehlende/leere Datei -> `([], None)`
    (=> Status UNBESTAETIGT, keine Freigabe).
    """
    if not os.path.exists(csv_pfad):
        return [], None
    with open(csv_pfad, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        if reader.fieldnames is None:
            return [], None  # komplett leere Datei
        if reader.fieldnames != SPALTEN:
            if reader.fieldnames == ALTSPALTEN:
                return None, (
                    "CSV hat das alte Schema ({a}). Bitte migrieren auf "
                    "{n}: fix_datum nach datum, Pflicht bei gefixt, "
                    "leer bei offen/kein_pflichtfehler."
                    ).format(a=";".join(ALTSPALTEN), n=";".join(SPALTEN))
            return None, ("CSV-Header unerkannt: {h!r} (erwartet: {e})"
                          ).format(h=list(reader.fieldnames),
                                   e=";".join(SPALTEN))
        rows = list(reader)

    def nicht_leer(r):
        if None in r:  # zu viele Felder
            return True
        return any((r.get(s) or "").strip() for s in SPALTEN)

    return [r for r in rows if nicht_leer(r)], None


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


def _roh(zeile):
    return {s: (zeile.get(s) or "").strip() for s in SPALTEN}


def validiere(zeile, idx):
    r = _roh(zeile)
    fehler = []
    if not ID_RE.match(r["id"]):
        fehler.append(f"Zeile {idx}: ungültige id (erwartet SF-NNN)")
    datum = None
    if not DATUM_RE.match(r["datum"]):
        fehler.append(f"Zeile {idx}: ungültiges datum (erwartet YYYY-MM-DD)")
    else:
        datum = _datum_parse(r["datum"])
        if datum is None:
            fehler.append(
                f"Zeile {idx}: datum {r['datum']!r} existiert nicht")
    if r["typ"] not in PFLICHTFEHLER_TYPEN:
        fehler.append(f"Zeile {idx}: typ {r['typ']!r} nicht in "
                      f"{list(PFLICHTFEHLER_TYPEN)}")
    if r["status"] not in GUELTIGE_STATUS:
        fehler.append(f"Zeile {idx}: status {r['status']!r} "
                      f"nicht in {list(GUELTIGE_STATUS)}")
    if r["status"] == "gefixt":
        if not DATUM_RE.match(r["fix_datum"]):
            fehler.append(f"Zeile {idx}: status gefixt ohne gültiges "
                          f"fix_datum (Pflichtfeld, YYYY-MM-DD)")
        else:
            fix = _datum_parse(r["fix_datum"])
            if fix is None:
                fehler.append(
                    f"Zeile {idx}: fix_datum {r['fix_datum']!r} "
                    f"existiert nicht")
            elif datum is not None and fix < datum:
                fehler.append(
                    f"Zeile {idx}: fix_datum {r['fix_datum']} vor "
                    f"Meldedatum {r['datum']}")
    elif r["fix_datum"]:
        fehler.append(
            f"Zeile {idx}: fix_datum nur bei status gefixt "
            f"(hier: {r['status']!r}, Feld leer lassen)")
    return fehler


def fenster_berechnen(zeilen):
    """(offen_anzahl, letztes_fix, fenster_ende, n_gefixt, typ_counter).

    - `offen` blockiert das Stable-Kriterium vollständig (wird als
      `offen_anzahl` mitgezählt, unabhängig von Fenstern).
    - `gefixt` zählt vom **fix_datum** (Fenster-Ende = letztes
      fix_datum + 14 Tage).
    - `kein_pflichtfehler` zählt nie.

    `letztes_fix` ist `(fix_datum, id)` oder None; `fenster_ende`
    ist das Datum oder None.
    """
    offen = 0
    fixes = []
    typ_counter = {}
    for z in zeilen:
        r = _roh(z)
        if r["typ"] in PFLICHTFEHLER_TYPEN:
            typ_counter[r["typ"]] = typ_counter.get(r["typ"], 0) + 1
        if r["status"] == "offen":
            offen += 1
        elif r["status"] == "gefixt":
            fix = _datum_parse(r["fix_datum"])
            if fix is not None:
                fixes.append((fix, r["id"]))
    if not fixes:
        return offen, None, None, 0, typ_counter
    letztes = max(fixes)
    return (offen, letztes, letztes[0] + timedelta(days=FENSTER_TAGE),
            len(fixes), typ_counter)


def _add_validiere(datum, fix_datum, typ, status):
    fehler = []
    d = _datum_parse(datum)
    if d is None:
        fehler.append(f"ungültiges Datum {datum!r} (YYYY-MM-DD)")
    f = _datum_parse(fix_datum) if fix_datum else None
    if typ not in PFLICHTFEHLER_TYPEN:
        fehler.append(f"typ {typ!r} nicht in {list(PFLICHTFEHLER_TYPEN)}")
    if status not in GUELTIGE_STATUS:
        fehler.append(f"status {status!r} nicht in {list(GUELTIGE_STATUS)}")
    if status == "gefixt" and f is None:
        fehler.append("status gefixt braucht fix_datum (2. Feld von --add)")
    elif status == "gefixt" and f is not None and d is not None \
            and f < d:
        fehler.append(f"fix_datum {fix_datum} vor Meldedatum {datum}")
    elif status != "gefixt" and fix_datum:
        fehler.append("fix_datum (2. Feld) nur bei status gefixt — "
                      "bei offen/kein_pflichtfehler leer lassen")
    return fehler


def main():
    p = argparse.ArgumentParser(description="Stable-Fenster-Tracker")
    p.add_argument("--csv", default="stable_fenster.csv")
    p.add_argument("--heute", default=None,
                   help="Referenz-Datum YYYY-MM-DD (Default: heute)")
    p.add_argument("--add", default=None,
                   help='neue Zeile anhängen: "datum;fix_datum;typ;'
                        'status;quelle" (id wird automatisch vergeben)')
    args = p.parse_args()

    if args.heute:
        heute = _datum_parse(args.heute)
        if heute is None:
            print(f"Fehler: ungültiges --heute {args.heute!r} "
                  f"(YYYY-MM-DD)", file=sys.stderr)
            return 1
    else:
        heute = date.today()

    zeilen, laadfehler = lade(args.csv)
    if laadfehler:
        print(f"Fehler: {laadfehler}", file=sys.stderr)
        return 1

    if args.add:
        teile = [t.strip() for t in args.add.split(";")]
        if len(teile) != 5:
            print('Fehler: --add erwartet "datum;fix_datum;typ;status;'
                  'quelle"', file=sys.stderr)
            return 1
        datum, fix_datum, typ, status, quelle = teile
        fehler = _add_validiere(datum, fix_datum, typ, status)
        if fehler:
            for f in fehler:
                print(f"Fehler: {f}", file=sys.stderr)
            return 1
        zeilen.append({"id": naechste_id(zeilen), "datum": datum,
                       "fix_datum": fix_datum, "typ": typ,
                       "status": status, "quelle": quelle})
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

    offen, letztes, fenster_ende, n_gefixt, typ_counter = \
        fenster_berechnen(zeilen)
    fp = sum(1 for z in zeilen if _roh(z)["status"] == "kein_pflichtfehler")

    print("=== STABLE-FENSTER ===", file=sys.stderr)
    print(f"Referenz-Datum: {heute.isoformat()}", file=sys.stderr)
    print(f"Einträge: {len(zeilen)} (offen: {offen}, gefixt: {n_gefixt}, "
          f"False-Positives: {fp})", file=sys.stderr)
    print("Aggregate je Typ:", file=sys.stderr)
    for typ in PFLICHTFEHLER_TYPEN:
        print(f"  {typ}: {typ_counter.get(typ, 0)}", file=sys.stderr)

    if offen:
        print(f"Status: NICHT ERFÜLLT — {offen} offener Pflichtfehler "
              f"blockiert das Stable-Kriterium vollständig", file=sys.stderr)
        return 2
    if fenster_ende is None:
        print("Status: UNBESTAETIGT — keine zählenden Pflichtfehler in "
              "der CSV; keine Freigabe (leere/nicht zählende Datenbasis "
              "bestätigt das Kriterium nicht)", file=sys.stderr)
        return 2
    if heute < fenster_ende:
        rest = (fenster_ende - heute).days
        print(f"Status: FENSTER LÄUFT NOCH — letzter Fix {letztes[1]} "
              f"am {letztes[0].isoformat()} + {FENSTER_TAGE} Tage = "
              f"{fenster_ende.isoformat()} (noch {rest} Tage)",
              file=sys.stderr)
        return 2
    if heute == fenster_ende:
        print(f"Status: FENSTER ENDET HEUTE ({fenster_ende.isoformat()}) "
              f"— morgen Stable-fähig", file=sys.stderr)
        return 2
    print(f"Status: STABLE-KRITERIUM ERFÜLLT seit {fenster_ende.isoformat()} "
          f"(14 Tage ohne Pflichtfehler nach letztem Fix {letztes[1]} "
          f"am {letztes[0].isoformat()})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
