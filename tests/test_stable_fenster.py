#!/usr/bin/env python3
"""Unit-Tests fuer stable_fenster.py (synthetische Fixtures,
public-safe: keine Spieltexte).

Deckt die QA-Korrektur 2026-10-28 ab:
- `offen` blockiert das Stable-Kriterium vollstaendig (niemals gruen)
- `gefixt` laeuft vom fix_datum (nicht vom Meldedatum)
- leere/nicht zählende CSV => UNBESTAETIGT (keine Freigabe)
- Exit-Codes: 0 = gruen, 1 = Input-Fehler, 2 = nicht-gruen
- Schema-Change: id;datum;fix_datum;typ;status;quelle
"""

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
import stable_fenster as sf  # noqa: E402

SCRIPT = os.path.join(BASE, "stable_fenster.py")


class TestValidiere(unittest.TestCase):
    def ok(self):
        return {"id": "SF-001", "datum": "2026-10-20", "fix_datum": "",
                "typ": "en_rest", "status": "offen", "quelle": "Test"}

    def ok_gefixt(self):
        return {"id": "SF-001", "datum": "2026-10-20",
                "fix_datum": "2026-10-21", "typ": "en_rest",
                "status": "gefixt", "quelle": "Test"}

    def test_gueltig_offen(self):
        self.assertEqual(sf.validiere(self.ok(), 2), [])

    def test_gueltig_gefixt(self):
        self.assertEqual(sf.validiere(self.ok_gefixt(), 2), [])

    def test_schlechte_id(self):
        z = self.ok()
        z["id"] = "X-1"
        self.assertTrue(any("id" in e for e in sf.validiere(z, 2)))

    def test_schlechtes_datum(self):
        z = self.ok()
        z["datum"] = "20.10.2026"
        self.assertTrue(any("datum" in e for e in sf.validiere(z, 2)))

    def test_datum_existiert_nicht(self):
        z = self.ok()
        z["datum"] = "2026-13-99"
        self.assertTrue(any("existiert nicht" in e for e in
                            sf.validiere(z, 2)))

    def test_schlechter_typ(self):
        z = self.ok()
        z["typ"] = "stilwunsch"
        self.assertTrue(any("typ" in e for e in sf.validiere(z, 2)))

    def test_schlechter_status(self):
        z = self.ok()
        z["status"] = "wip"
        self.assertTrue(any("status" in e for e in sf.validiere(z, 2)))

    def test_gefixt_ohne_fix_datum(self):
        z = self.ok_gefixt()
        z["fix_datum"] = ""
        self.assertTrue(any("fix_datum" in e for e in sf.validiere(z, 2)))

    def test_gefixt_fix_datum_vor_meldedatum(self):
        z = self.ok_gefixt()
        z["fix_datum"] = "2026-10-19"
        self.assertTrue(any("vor Meldedatum" in e for e in
                            sf.validiere(z, 2)))

    def test_gefixt_fix_datum_existiert_nicht(self):
        z = self.ok_gefixt()
        z["fix_datum"] = "2026-02-30"
        self.assertTrue(any("existiert nicht" in e for e in
                            sf.validiere(z, 2)))

    def test_offen_mit_fix_datum(self):
        z = self.ok()
        z["fix_datum"] = "2026-10-25"
        self.assertTrue(any("fix_datum" in e for e in sf.validiere(z, 2)))

    def test_kein_pflichtfehler_mit_fix_datum(self):
        z = self.ok()
        z["status"] = "kein_pflichtfehler"
        z["fix_datum"] = "2026-10-25"
        self.assertTrue(any("fix_datum" in e for e in sf.validiere(z, 2)))


class TestFenster(unittest.TestCase):
    def zeile(self, id_, datum, typ="en_rest", status="offen",
              fix_datum=""):
        return {"id": id_, "datum": datum, "fix_datum": fix_datum,
                "typ": typ, "status": status, "quelle": ""}

    def test_leer(self):
        offen, letztes, ende, n, tc = sf.fenster_berechnen([])
        self.assertEqual(offen, 0)
        self.assertIsNone(letztes)
        self.assertIsNone(ende)
        self.assertEqual(n, 0)
        self.assertEqual(tc, {})

    def test_fenster_laeuft_vom_fix_datum(self):
        # Meldedatum 10-01, Fix 10-20 => Fenster laeuft bis 11-03,
        # NICHT bis 10-15 (Meldedatum + 14).
        zeilen = [self.zeile("SF-001", "2026-10-01", status="gefixt",
                             fix_datum="2026-10-20")]
        offen, letztes, ende, n, tc = sf.fenster_berechnen(zeilen)
        self.assertEqual(offen, 0)
        self.assertEqual(letztes[0], date(2026, 10, 20))
        self.assertEqual(ende, date(2026, 11, 3))  # 10-20 + 14 Tage
        self.assertEqual(n, 1)

    def test_neuester_fix_bestimmt_fenster(self):
        zeilen = [self.zeile("SF-001", "2026-10-01", status="gefixt",
                             fix_datum="2026-10-02"),
                  self.zeile("SF-002", "2026-10-20", status="gefixt",
                             fix_datum="2026-10-25")]
        offen, letztes, ende, n, tc = sf.fenster_berechnen(zeilen)
        self.assertEqual(letztes[0], date(2026, 10, 25))
        self.assertEqual(letztes[1], "SF-002")
        self.assertEqual(ende, date(2026, 11, 8))  # 10-25 + 14 Tage
        self.assertEqual(n, 2)

    def test_offen_wird_geschaut(self):
        zeilen = [self.zeile("SF-001", "2026-10-20")]
        offen, _, _, _, _ = sf.fenster_berechnen(zeilen)
        self.assertEqual(offen, 1)

    def test_false_positive_zahlt_nie(self):
        zeilen = [self.zeile("SF-001", "2026-10-20",
                             status="kein_pflichtfehler")]
        offen, letztes, ende, n, tc = sf.fenster_berechnen(zeilen)
        self.assertEqual(offen, 0)
        self.assertIsNone(letztes)
        self.assertIsNone(ende)
        self.assertEqual(n, 0)

    def test_typ_aggregate(self):
        zeilen = [self.zeile("SF-001", "2026-10-20", typ="grammatik"),
                  self.zeile("SF-002", "2026-10-21", typ="grammatik"),
                  self.zeile("SF-003", "2026-10-22", typ="absturz",
                             status="gefixt", fix_datum="2026-10-23")]
        offen, _, _, n, tc = sf.fenster_berechnen(zeilen)
        self.assertEqual(offen, 2)
        self.assertEqual(n, 1)
        self.assertEqual(tc, {"grammatik": 2, "absturz": 1})


class TestLade(unittest.TestCase):
    def write(self, td, inhalt, name="sf.csv"):
        pfad = os.path.join(td, name)
        with open(pfad, "w", encoding="utf-8", newline="") as fh:
            fh.write(inhalt)
        return pfad

    def test_fehlende_datei(self):
        with tempfile.TemporaryDirectory() as td:
            zeilen, fehler = sf.lade(os.path.join(td, "fehlt.csv"))
            self.assertEqual(zeilen, [])
            self.assertIsNone(fehler)

    def test_komplett_leere_datei(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = self.write(td, "")
            zeilen, fehler = sf.lade(pfad)
            self.assertEqual(zeilen, [])
            self.assertIsNone(fehler)

    def test_nur_header(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = self.write(td, "id;datum;fix_datum;typ;status;quelle\n")
            zeilen, fehler = sf.lade(pfad)
            self.assertEqual(zeilen, [])
            self.assertIsNone(fehler)

    def test_altes_schema_wird_meldet(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = self.write(
                td, "id;datum;typ;status;quelle\n"
                    "SF-001;2026-10-20;en_rest;gefixt;x\n")
            zeilen, fehler = sf.lade(pfad)
            self.assertIsNone(zeilen)
            self.assertIn("migrieren", fehler)

    def test_unbekannter_header(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = self.write(td, "id;datum;typ\nSF-001;2026-10-20;x\n")
            zeilen, fehler = sf.lade(pfad)
            self.assertIsNone(zeilen)
            self.assertIn("unerkannt", fehler)

    def test_valide_zeilen(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = self.write(
                td, "id;datum;fix_datum;typ;status;quelle\n"
                    "SF-001;2026-10-20;2026-10-21;en_rest;gefixt;x\n"
                    "SF-002;2026-10-28;;text_breite;offen;y\n")
            zeilen, fehler = sf.lade(pfad)
            self.assertIsNone(fehler)
            self.assertEqual(len(zeilen), 2)
            self.assertEqual(zeilen[1]["fix_datum"], "")


class TestNaechsteId(unittest.TestCase):
    def test_leer(self):
        self.assertEqual(sf.naechste_id([]), "SF-001")

    def test_anhaengen(self):
        zeilen = [{"id": "SF-007", "datum": "2026-10-20", "typ": "absturz",
                   "status": "offen", "quelle": ""}]
        self.assertEqual(sf.naechste_id(zeilen), "SF-008")


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True)

    def test_offen_blockiert_vollstaendig(self):
        # QA-Repro: `offen` vom 01.10. => am 28.10. NICHT gruen,
        # obwohl > 14 Tage vergangen sind.
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            p1 = self.run_cli("--csv", pfad, "--add",
                              "2026-10-01;;en_rest;offen;Beta v0.1.7")
            self.assertEqual(p1.returncode, 2, p1.stderr)
            self.assertIn("offener Pflichtfehler", p1.stderr)

            p2 = self.run_cli("--csv", pfad, "--heute", "2026-10-28")
            self.assertEqual(p2.returncode, 2, p2.stderr)
            self.assertIn("NICHT ERFÜLLT", p2.stderr)
            self.assertIn("blockiert", p2.stderr)
            self.assertNotIn("STABLE-KRITERIUM ERFÜLLT", p2.stderr)

    def test_leeres_csv_unbestätigt(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "leer.csv")
            with open(pfad, "w", encoding="utf-8") as fh:
                fh.write("id;datum;fix_datum;typ;status;quelle\n")
            p = self.run_cli("--csv", pfad, "--heute", "2026-11-19")
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertIn("UNBESTAETIGT", p.stderr)

    def test_fehlende_csv_unbestätigt(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "fehlt.csv")
            p = self.run_cli("--csv", pfad, "--heute", "2026-11-19")
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertIn("UNBESTAETIGT", p.stderr)

    def test_gruen_nur_nach_14_tagen_ab_fix(self):
        # Fix am 14.10. => Fenster-Ende 28.10.:
        # 27.10. laeuft, 28.10. endet heute (morgen Stable-fähig),
        # 29.10. gruen.
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            # --heute bewusst gesetzt: Test muss an jedem
            # Lauf-Tag deterministisch sein.
            p = self.run_cli("--csv", pfad, "--heute", "2026-10-15",
                             "--add",
                             "2026-10-12;2026-10-14;grammatik;gefixt;x")
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertIn("FENSTER LÄUFT NOCH", p.stderr)

            p27 = self.run_cli("--csv", pfad, "--heute", "2026-10-27")
            self.assertEqual(p27.returncode, 2, p27.stderr)
            self.assertIn("FENSTER LÄUFT NOCH", p27.stderr)

            p28 = self.run_cli("--csv", pfad, "--heute", "2026-10-28")
            self.assertEqual(p28.returncode, 2, p28.stderr)
            self.assertIn("ENDET HEUTE", p28.stderr)

            p29 = self.run_cli("--csv", pfad, "--heute", "2026-10-29")
            self.assertEqual(p29.returncode, 0, p29.stderr)
            self.assertIn("STABLE-KRITERIUM ERFÜLLT", p29.stderr)

    def test_offen_zaehlt_gegen_alte_gruene_zeit(self):
        # Alter Fix (Fenster laengst vorbei) + neuer offener Fehler
        # => NICHT gruen.
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            self.run_cli("--csv", pfad, "--add",
                         "2026-09-01;2026-09-02;grafik;gefixt;a")
            self.run_cli("--csv", pfad, "--add",
                         "2026-10-20;;absturz;offen;b")
            p = self.run_cli("--csv", pfad, "--heute", "2026-10-28")
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertIn("NICHT ERFÜLLT", p.stderr)

    def test_gefixt_ohne_fix_datum_inputfehler(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            with open(pfad, "w", encoding="utf-8") as fh:
                fh.write("id;datum;fix_datum;typ;status;quelle\n"
                         "SF-001;2026-10-20;;en_rest;gefixt;x\n")
            p = self.run_cli("--csv", pfad, "--heute", "2026-11-01")
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn("fix_datum", p.stderr)

    def test_altes_schema_inputfehler(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "alt.csv")
            with open(pfad, "w", encoding="utf-8") as fh:
                fh.write("id;datum;typ;status;quelle\n"
                         "SF-001;2026-10-20;en_rest;gefixt;x\n")
            p = self.run_cli("--csv", pfad, "--heute", "2026-11-01")
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn("migrieren", p.stderr)

    def test_ungueltiges_heute(self):
        p = self.run_cli("--heute", "20.11.2026")
        self.assertEqual(p.returncode, 1)
        self.assertIn("--heute", p.stderr)

    def test_add_gefixt_ohne_fix_datum_schreibt_nichts(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            p = self.run_cli("--csv", pfad, "--add",
                             "2026-11-04;;grammatik;gefixt;x")
            self.assertEqual(p.returncode, 1)
            self.assertIn("fix_datum", p.stderr)
            zeilen, fehler = sf.lade(pfad)
            self.assertIsNone(fehler)
            self.assertEqual(zeilen, [])

    def test_add_fix_datum_vor_datum(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            p = self.run_cli("--csv", pfad, "--add",
                             "2026-11-04;2026-11-01;grammatik;gefixt;x")
            self.assertEqual(p.returncode, 1)
            self.assertIn("vor Meldedatum", p.stderr)

    def test_add_falsche_feldanzahl(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            # altes 4-Feld-Format => abgewiesen
            p = self.run_cli("--csv", pfad, "--add",
                             "2026-11-04;grammatik;offen;x")
            self.assertEqual(p.returncode, 1)
            self.assertIn("--add erwartet", p.stderr)

    def test_add_dann_fenster(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            p1 = self.run_cli("--csv", pfad, "--add",
                              "2026-11-04;2026-11-05;grammatik;gefixt;"
                              "Beta v0.1.7")
            # Dateigrundlage geschrieben, aber Status nicht gruen
            # (Fenster laeuft) => Exit 2.
            self.assertEqual(p1.returncode, 2, p1.stderr)
            self.assertTrue(os.path.exists(pfad))
            zeilen, fehler = sf.lade(pfad)
            self.assertIsNone(fehler)
            self.assertEqual(len(zeilen), 1)
            self.assertEqual(zeilen[0]["id"], "SF-001")
            self.assertEqual(zeilen[0]["fix_datum"], "2026-11-05")

            p2 = self.run_cli("--csv", pfad, "--heute", "2026-11-06")
            self.assertEqual(p2.returncode, 2, p2.stderr)
            self.assertIn("FENSTER", p2.stderr)
            self.assertIn("2026-11-19", p2.stderr)  # 11-05 + 14 Tage

            p3 = self.run_cli("--csv", pfad, "--heute", "2026-11-20")
            self.assertEqual(p3.returncode, 0, p3.stderr)
            self.assertIn("STABLE-KRITERIUM ERFÜLLT", p3.stderr)
            self.assertIn("2026-11-19", p3.stderr)

    def test_zweite_zeile_id(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            for i in range(2):
                p = self.run_cli("--csv", pfad, "--add",
                                 f"2026-11-0{i + 4};;grammatik;offen;x")
                self.assertEqual(p.returncode, 2, p.stderr)
            zeilen, fehler = sf.lade(pfad)
            self.assertIsNone(fehler)
            self.assertEqual([z["id"] for z in zeilen],
                             ["SF-001", "SF-002"])


if __name__ == "__main__":
    unittest.main()
