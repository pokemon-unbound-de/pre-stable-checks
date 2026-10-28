#!/usr/bin/env python3
"""Unit-Tests fuer buffer_validator.py (synthetische Fixtures,
public-safe: keine Spieltexte)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
import buffer_validator as bv  # noqa: E402


class TestPcsLen(unittest.TestCase):
    def test_lateinisch(self):
        self.assertEqual(bv.pcs_len("Rost. Schwert"), 13)

    def test_umlaut_ein_byte(self):
        # Umlaute sind 1 PCS-Byte (im Gegensatz zu UTF-8: 2 Byte)
        self.assertEqual(bv.pcs_len("Glühwürmch."), 11)
        self.assertEqual(bv.pcs_len("äöüÄÖÜ"), 6)

    def test_ss_ein_byte(self):
        self.assertEqual(bv.pcs_len("ß"), 1)

    def test_apostroph(self):
        self.assertEqual(bv.pcs_len("It's"), 4)

    def test_unmapped_wirft(self):
        with self.assertRaises(ValueError):
            bv.pcs_len("€")


class TestC1UnknownEscapes(unittest.TestCase):
    def test_bekannte_einzeiger(self):
        s = "a" + "\\n" + "\\l" + "\\p" + "\\e" + "\\d" + "\\r"
        s += "\\." + "\\<" + "\\>" + "\\+" + "b"
        self.assertEqual(bv.c1_unknown_escapes(s), [])

    def test_bekannte_zeigezer(self):
        s = ("x" + "\\pk" + " " + "\\mn" + "\\Ke" + "\\Bl" + "\\Lo"
             + "\\Ck" + "\\Lv" + "\\qo" + "\\qc" + "\\sm" + "\\sf"
             + "\\au" + "\\ad" + "\\al" + "\\ar" + "y")
        self.assertEqual(bv.c1_unknown_escapes(s), [])

    def test_po_ohne_buchstabe_danach(self):
        # \Po am Ende / vor Nicht-Buchstabe ist der Name-Code
        self.assertEqual(bv.c1_unknown_escapes("\\Po " + "abc"), [])
        self.assertEqual(bv.c1_unknown_escapes("x\\Po"), [])

    def test_po_mit_buchstabe_danach(self):
        # \Pok…: 'Po' scheitert am Lookahead (Buchstabe folgt), und
        # großes 'P' ist kein 1-Zeiger-Escape -> wird gemeldet
        # (wie der Korpus-Fall \PoIVs).
        self.assertEqual(bv.c1_unknown_escapes("\\Pok"), ["\\P"])

    def test_grosses_p_allein(self):
        # \P ohne 'o' hinterher: keine bekannte Escape-Form
        self.assertEqual(bv.c1_unknown_escapes("a\\Pb"), ["\\P"])
        self.assertEqual(bv.c1_unknown_escapes("a\\P"), ["\\P"])

    def test_ziffer(self):
        self.assertEqual(bv.c1_unknown_escapes("a\\5b"), ["\\5"])

    def test_backslash_am_ende(self):
        self.assertEqual(bv.c1_unknown_escapes("a\\"),
                         ["Backslash am Zeilenende"])

    def test_doppelbackslash(self):
        # '\\' ist kein Escape in der Grammatik: jeder Backslash wird
        # einzeln gemeldet (nächster Zeichen ist jeweils '\').
        dets = bv.c1_unknown_escapes("\\\\")
        self.assertEqual(len(dets), 2)
        self.assertEqual(dets[0], "\\\\")
        self.assertEqual(dets[1], "Backslash am Zeilenende")


class TestC2QuoteFindings(unittest.TestCase):
    def test_gepaart_qc(self):
        self.assertEqual(bv.c2_quote_findings("\\qoA\\qc"), [])

    def test_gepaart_qo(self):
        # Korpus-Form: \qo schliesst Zitate ebenfalls (gueltig)
        self.assertEqual(bv.c2_quote_findings("\\qoA\\qo"), [])

    def test_zwei_paare(self):
        self.assertEqual(
            bv.c2_quote_findings("\\qoA\\qo, B\\qo C\\qc"), [])

    def test_mischpaare(self):
        self.assertEqual(
            bv.c2_quote_findings("\\qoA\\qc B\\qo C\\qo"), [])

    def test_ungeschlossen(self):
        dets = bv.c2_quote_findings("x\\qoA")
        self.assertEqual(len(dets), 1)
        self.assertIn("ungeschlossen", dets[0])

    def test_qc_ohne_oeffnung(self):
        dets = bv.c2_quote_findings("\\qcA\\qoB")
        self.assertEqual(len(dets), 1)
        self.assertIn("ohne Oeffnung", dets[0])

    def test_keine_zitate(self):
        self.assertEqual(bv.c2_quote_findings("Einfacher Text"), [])


class TestBracketChecks(unittest.TestCase):
    def codes(self, text):
        return [c for c, _ in bv.check_text(text)]

    def test_gueltige_formen(self):
        gueltig = (
            "[#FC0106]", "[FC0106]",          # FC + 2 Hex
            "[#FC010600]", "[FC1355]",        # FC + 4 Hex
            "[#FC01060000]",                  # FC + 6 Hex
            "[#FC040D0E0F]",                  # FC + 8 Hex (3 Argumente)
            "[#FD0F]", "[FD0F]", "[#FD01]",   # Puffer-Makros
            "[#F8]", "[#F7]", "[#F9]",        # Präfixe ohne Argument
            "[#F800]", "[#F80A]", "[#F912]",  # Präfix + 2 Hex
            "[#0A]", "[#B9]", "[#FA]", "[#30]",  # generische 2-Hex
            "[player]", "[buffer1]", "[buffer2]", "[buffer3]",
            "[kun]", "[rival]", "[up]", "[down]",
            "[left]", "[right]",
        )
        for t in gueltig:
            self.assertEqual(self.codes(t), [], msg=t)

    def test_malformed(self):
        malformed = (
            "[#FC013]",          # 3 Hex
            "[#FC010600000000]",  # 12 Hex
            "[#FC]",           # 0 Hex
            "[FC]",
            "[#FD0102]",       # FD mit 4 Hex
            "[#FD0]",          # FD mit 1 Hex
            "[#F80]",          # Präfix mit 1 Hex
            "[#F80000]",       # Präfix mit 4 Hex
            "[foo]",           # unbekanntes Makronamen
            "[#FEFD02FC09]",   # Korpus-Fall: 3 Codes in einer Klammer
            "[#FC]",           # leerer FC-Teil
        )
        for t in malformed:
            self.assertEqual(self.codes(t), ["malformed_bracket"], msg=t)

    def test_fc_odd_shape(self):
        # 10-Hex-FC: Review-Befund (C4), kein Formatfehler (C3)
        for t in ("[#FC134BFC0600]", "[FC134BFC0600]", "[#FC1355FC0600]"):
            self.assertEqual(self.codes(t), ["fc_odd_shape"], msg=t)

    def test_mehrere_klammern(self):
        dets = [c for c, _ in bv.check_text("[#FD01][foo][#FC134BFC0600]")]
        self.assertEqual(dets, ["malformed_bracket", "fc_odd_shape"])

    def test_c1_und_c3_zusammen(self):
        dets = [(c) for c, _ in bv.check_text("a\\Pb[foo]")]
        self.assertEqual(dets, ["unknown_escape", "malformed_bracket"])


class TestLinePixelWidths(unittest.TestCase):
    def test_leer(self):
        self.assertEqual(bv.line_pixel_widths(""), [0])

    def test_standardbreite(self):
        # a/b/c = je 6 px
        self.assertEqual(bv.line_pixel_widths("abc"), [18])

    def test_punkt_fuenf_px(self):
        # '.' = PCS-Byte 0xAD = 5 px
        self.assertEqual(bv.line_pixel_widths("."), [5])

    def test_zeilengrenzen(self):
        self.assertEqual(bv.line_pixel_widths("a\\lb\\nc"), [6, 6, 6])
        self.assertEqual(bv.line_pixel_widths("a\\pb"), [6, 6])

    def test_zwei_branche_zeilen(self):
        # zwei aufeinanderfolgende Zeilenbrüche -> leere Zeile dazwischen
        self.assertEqual(bv.line_pixel_widths("a\\l\\nb"), [6, 0, 6])

    def test_fd_54_px(self):
        self.assertEqual(bv.line_pixel_widths("[#FD01]"), [54])
        self.assertEqual(bv.line_pixel_widths("ab[#FD01]cd"), [78])

    def test_fc_null_px(self):
        self.assertEqual(bv.line_pixel_widths("[#FC0106]"), [0])
        self.assertEqual(bv.line_pixel_widths("a[#FC01060000]b"), [12])

    def test_button_makro(self):
        # [#F8] = PCS-Byte 0xF8 -> Glyph-Breite 6 px
        self.assertEqual(bv.line_pixel_widths("[#F8]"), [6])
        self.assertEqual(bv.line_pixel_widths("[#F800]"), [6])

    def test_steuerbyte_null_px(self):
        # FA/FB/FE = Steuer-Bytes ohne Breite (Referenz-Semantik)
        for t in ("[#FA]", "[#FB]", "[#FE]"):
            self.assertEqual(bv.line_pixel_widths(t), [0], msg=t)

    def test_generisches_byte(self):
        # [#0A] = PCS-Byte 0x0A -> Glyph-Breite 6 px
        self.assertEqual(bv.line_pixel_widths("[#0A]"), [6])

    def test_escapes_keine_breite(self):
        self.assertEqual(bv.line_pixel_widths("\\qoA\\qc"), [6])
        self.assertEqual(bv.line_pixel_widths("\\au\\ad"), [0])

    def test_unmapped_konservativ_sechs(self):
        self.assertEqual(bv.line_pixel_widths("€"), [6])

    def test_ungeschlossene_klammer(self):
        self.assertEqual(bv.line_pixel_widths("a["), [6])


if __name__ == "__main__":
    unittest.main()
