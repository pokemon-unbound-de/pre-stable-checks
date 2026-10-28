#!/usr/bin/env python3
"""Unit-Tests fuer stable_fenster.py (synthetische Fixtures,
public-safe: keine Spieltexte)."""

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
        return {"id": "SF-001", "datum": "2026-10-20", "typ": "en_rest",
                "status": "offen", "quelle": "Test"}

    def test_gueltig(self):
        self.assertEqual(sf.validiere(self.ok(), 2), [])

    def test_schlechte_id(self):
        z = self.ok()
        z["id"] = "X-1"
        self.assertTrue(any("id" in e for e in sf.validiere(z, 2)))

    def test_schlechtes_datum(self):
        z = self.ok()
        z["datum"] = "20.10.2026"
        self.assertTrue(any("datum" in e for e in sf.validiere(z, 2)))

    def test_schlechter_typ(self):
        z = self.ok()
        z["typ"] = "stilwunsch"
        self.assertTrue(any("typ" in e for e in sf.validiere(z, 2)))

    def test_schlechter_status(self):
        z = self.ok()
        z["status"] = "wip"
        self.assertTrue(any("status" in e for e in sf.validiere(z, 2)))


class TestFenster(unittest.TestCase):
    def zeile(self, id_, datum, typ="en_rest", status="offen"):
        return {"id": id_, "datum": datum, "typ": typ, "status": status,
                "quelle": ""}

    def test_leer(self):
        letztes, ende, n, tc = sf.fenster_berechnen([], date(2026, 11, 1))
        self.assertIsNone(letztes)
        self.assertIsNone(ende)
        self.assertEqual(n, 0)
        self.assertEqual(tc, {})

    def test_fenster_ende(self):
        zeilen = [self.zeile("SF-001", "2026-10-20"),
                  self.zeile("SF-002", "2026-10-25", status="gefixt")]
        letztes, ende, n, tc = sf.fenster_berechnen(
            zeilen, date(2026, 11, 1))
        self.assertEqual(letztes[0], date(2026, 10, 25))
        self.assertEqual(ende, date(2026, 11, 8))  # 10-25 + 14 Tage
        self.assertEqual(n, 2)

    def test_false_positive_zahlt_nie(self):
        zeilen = [self.zeile("SF-001", "2026-10-20",
                             status="kein_pflichtfehler")]
        letztes, ende, n, tc = sf.fenster_berechnen(
            zeilen, date(2026, 11, 1))
        self.assertIsNone(letztes)
        self.assertEqual(n, 0)

    def test_typ_aggregate(self):
        zeilen = [self.zeile("SF-001", "2026-10-20", typ="grammatik"),
                  self.zeile("SF-002", "2026-10-21", typ="grammatik"),
                  self.zeile("SF-003", "2026-10-22", typ="absturz")]
        letztes, ende, n, tc = sf.fenster_berechnen(
            zeilen, date(2026, 11, 1))
        self.assertEqual(tc, {"grammatik": 2, "absturz": 1})


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

    def test_add_dann_fenster(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            p1 = self.run_cli("--csv", pfad, "--add",
                              "2026-11-04;grammatik;offen;Beta v0.1.7")
            self.assertEqual(p1.returncode, 0, p1.stderr)
            self.assertTrue(os.path.exists(pfad))
            zeilen = sf.lade(pfad)
            self.assertEqual(len(zeilen), 1)
            self.assertEqual(zeilen[0]["id"], "SF-001")
            self.assertEqual(zeilen[0]["typ"], "grammatik")

            p2 = self.run_cli("--csv", pfad, "--heute", "2026-11-05")
            self.assertEqual(p2.returncode, 0, p2.stderr)
            self.assertIn("FENSTER", p2.stderr)
            self.assertIn("2026-11-18", p2.stderr)  # 11-04 + 14 Tage

            p3 = self.run_cli("--csv", pfad, "--heute", "2026-11-19")
            self.assertEqual(p3.returncode, 0, p3.stderr)
            self.assertIn("STABLE-KRITERIUM ERFÜLLT", p3.stderr)
            self.assertIn("2026-11-18", p3.stderr)

    def test_leeres_csv_erfuellt(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "leer.csv")
            with open(pfad, "w", encoding="utf-8") as fh:
                fh.write("id;datum;typ;status;quelle\n")
            p = self.run_cli("--csv", pfad, "--heute", "2026-11-19")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("KEIN Pflichtfehler erfasst", p.stderr)

    def test_add_ungueltiger_typ_schreibt_nichts(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            p = self.run_cli("--csv", pfad, "--add",
                             "2026-11-04;stilwunsch;offen;x")
            self.assertEqual(p.returncode, 1)
            self.assertIn("nicht in", p.stderr)
            # Validierung vor dem Schreiben: Datei bleibt leer
            self.assertEqual(sf.lade(pfad), [])

    def test_add_ungueltiges_datum(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            p = self.run_cli("--csv", pfad, "--add",
                             "20.11.2026;grammatik;offen;x")
            self.assertEqual(p.returncode, 1)
            self.assertIn("ungültiges Datum", p.stderr)

    def test_zweite_zeile_id(self):
        with tempfile.TemporaryDirectory() as td:
            pfad = os.path.join(td, "sf.csv")
            for i in range(2):
                p = self.run_cli("--csv", pfad, "--add",
                                 f"2026-11-0{i + 4};grammatik;offen;x")
                self.assertEqual(p.returncode, 0, p.stderr)
            zeilen = sf.lade(pfad)
            self.assertEqual([z["id"] for z in zeilen],
                             ["SF-001", "SF-002"])


if __name__ == "__main__":
    unittest.main()
