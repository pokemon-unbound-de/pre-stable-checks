#!/usr/bin/env python3
"""Unit-Tests fuer buffer_validator.py (synthetische Fixtures,
public-safe: keine Spieltexte)."""

import os
import re
import sys
import tempfile
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
            # Encoder-Regel: # + GERADE Hex = gültige Rohbytefolge
            # (differenziell gegen tools/pcs_encode.py verifiziert):
            "[#AB]", "[#ABCD]", "[#ab12]",    # gerade Hex (auch klein)
            "[#FC]",                          # Rohbyte 0xFC (2 Hex)
            "[#FD0102]",                      # 6 Hex
            "[#F80000]",                      # 6 Hex
            "[#FC010600000000]",              # 14 Hex
            "[#FEFD02FC09]",                  # 10 Hex — ehemaliger
                                              # C3-Falschpositiv (Regressionsfall)
        )
        for t in gueltig:
            self.assertEqual(self.codes(t), [], msg=t)

    def test_malformed(self):
        # # -Familie: UNGERADE Hex oder nicht-hex => C3
        # (Encoder: bytes.fromhex wirft ValueError bzw. Regex matcht
        # nicht => nicht encodierbar, tools/pcs_encode.py @ 2026-10-28)
        malformed = (
            "[#FC013]",          # 5 Hex (ungerade)
            "[#FD0]",            # 3 Hex (ungerade)
            "[#F80]",           # 3 Hex (ungerade)
            "[#ABC]",           # 3 Hex (ungerade)
            "[#ABCDE]",         # 5 Hex (ungerade)
            "[#XYZ]",           # nicht-hex
            "[#ZK9]",           # nicht-hex
            "[FC]",             # Kurzform-Familie: FC ohne Argument
            "[foo]",            # unbekanntes Makronamen
        )
        for t in malformed:
            self.assertEqual(self.codes(t), ["malformed_bracket"], msg=t)

    def test_fc_odd_shape(self):
        # FC + 10 Hex: C4 ist INFORMATIV (syntaktisch gültige
        # Rohbytefolge, semantisch zu prüfen) — kein C3.
        self.assertEqual(self.codes("[FC134BFC0600]"),["fc_odd_shape"])
        for t in ("[#FC134BFC0600]","[#FC1355FC0600]","[#FC1301FC0601FC0102]"):
            self.assertEqual(self.codes(t), [], msg=t)

    def test_mehrere_klammern(self):
        dets = [c for c, _ in bv.check_text("[#FD01][foo][#FC134BFC0600]")]
        self.assertEqual(dets, ["malformed_bracket"])

    def test_c1_und_c3_zusammen(self):
        dets = [(c) for c, _ in bv.check_text("a\\Pb[foo]")]
        self.assertEqual(dets, ["unknown_escape", "malformed_bracket"])


class TestEncoderDifferential(unittest.TestCase):
    """C3-Regel DIFFERENZIELL gegen den echten Encoder.

    Referenz: tools/pcs_encode.py (pokemon-unbound-de-web/review),
    Stand 2026-10-28. Der Encoder behandelt [#HH..] als Rohbytes:
        _RAW = re.compile(r"\\[#([0-9A-Fa-f]{2,})\\]")
        bytes.fromhex(rm.group(1))
    D. h. [#..] wird NUR dann als (gültiger) Code konsumiert, wenn der
    Inhalt GERADE Hex-Ziffern (>= 2) ist. Ungerade Hex -> fromhex
    ValueError; nicht-hex -> Regex matcht nicht (Code wird nicht
    konsumiert). Die C3-Regel des Validators muss genau dazu passen:
    gerade Hex = gueltig (kein C3), ungerade/nicht-hex = C3.
    """

    # Exakte Encoder-Referenz (Auszug, identisch zu tools/pcs_encode.py)
    _RAW = re.compile(r"\[#([0-9A-Fa-f]{2,})\]")

    @classmethod
    def _encoder_consumes_raw(cls, tok):
        """True, wenn der Encoder [#tok] als Rohbyte-Code konsumiert."""
        m = cls._RAW.match("[" + tok + "]")
        if not m:
            return False
        try:
            bytes.fromhex(m.group(1))
            return True
        except ValueError:
            return False

    # (Form, sollte-C3?) — C3 = nicht encodierbare Rohbytefolge
    FORMS = (
        ("#AB", False), ("#ABCD", False), ("#AB1234", False),
        ("#ab12", False), ("#FEFD02FC09", False),  # Korpus-Fall (Falschpositiv)
        ("#FC01", False), ("#FC010600000000", False),
        ("#FD0102", False), ("#F80000", False), ("#F8", False),
        ("#ABC", True),     # ungerade
        ("#ABCDE", True),   # ungerade
        ("#FC013", True),   # ungerade
        ("#XYZ", True),     # nicht-hex
        ("#ZK9", True),     # nicht-hex
    )

    def test_c3_matches_encoder(self):
        for tok, expect_c3 in self.FORMS:
            encodable = self._encoder_consumes_raw(tok)
            # Validator: C3 genau dann, wenn der Encoder die Form nicht
            # als Rohbyte-Code konsumiert.
            codes = [c for c, _ in bv.check_text("[" + tok + "]")
                     if c in ("malformed_bracket", "fc_odd_shape")]
            has_c3 = "malformed_bracket" in codes
            self.assertEqual(has_c3, expect_c3,
                             f"C3-Validator für {tok}")
            self.assertEqual(encodable, not expect_c3,
                             f"Encoder-Referenz für {tok}")
            # Konsistenz: Encoder konsumiert  <=>  kein C3
            self.assertEqual(encodable, not has_c3,
                             f"Differenz {tok}")

    def test_raw_combined_fc_is_valid_without_diagnostic(self):
        # FC + 10 Hex: Encoder konsumiert (gerade), Validator meldet
        # nur C4 (informativ), kein C3.
        codes = [c for c, _ in bv.check_text("[#FC134BFC0600]")]
        self.assertEqual(codes, [])

    def test_reference_escape_is_informative_without_normalization(self):
        text=r"Base[FC13]&EVs[FC13]\PoIVs"
        self.assertIn('reference_unknown_escape',[c for c,_ in bv.check_text(text,reference=True)])
        self.assertIn('unknown_escape',[c for c,_ in bv.check_text(text)])
        self.assertEqual(text,r"Base[FC13]&EVs[FC13]\PoIVs")

    def test_malformed_combined_raw_sequence_still_rejected(self):
        for text in ('[#FC134BFC060]','[#FC13ZZFC0600]'):
            self.assertIn('malformed_bracket',[c for c,_ in bv.check_text(text)])


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


class TestReport(unittest.TestCase):
    """Prüf-Abgrenzung + Urteil im Aggregat-Report (QA-Punkt 2):
    'N Befunde = formatgültig' darf kein Gesamturteil sein; C4 ist
    informativ und zählt nicht gegen die Formatgültigkeit."""

    def _korpus(self, td):
        pfad = os.path.join(td, "korpus.csv")
        rows = ["id;en;de;kategorie;ort"]
        # 1x C1 (unbekanntes Escape in DE), 1x C4 (informativ),
        # 1 gültige gerade Rohbytefolge (kein Befund, Regression).
        rows.append("K-001;Hi;Hallo \\P[#FEFD02FC09]abc;text;ort1")
        rows.append("K-002;Source \\P;[#FC134BFC0600]geht;text;ort2")
        rows.append("K-003;Clean;[#0A]gut;text;ort3")
        with open(pfad, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(rows) + "\n")
        return pfad

    def test_urteil_und_abgrenzung(self):
        with tempfile.TemporaryDirectory() as td:
            korpus = self._korpus(td)
            out = os.path.join(td, "out")
            rc = bv.run(korpus, None, out)
            self.assertEqual(rc, 0)
            with open(os.path.join(out, "format_report.md"),
                      encoding="utf-8") as fh:
                report = fh.read()
            self.assertIn("Pruef-Abgrenzung", report)
            self.assertIn("Formatgueltigkeits-Urteil", report)
            # C1 zählt formatrelevant, C4 nur informativ
            self.assertIn("(formatrelevant: 1, informativ: 1)", report)
            self.assertIn("- Formatrelevante Befunde: 1", report)
            self.assertIn("- Informative Befunde (keine Formatfehler): 1",
                          report)
            # gerade Rohbytefolge erzeugt KEIN C3-Befund mehr
            # (Tabellenzeile + Befund-Beispiele-Heading fehlen; der
            # Begriff kommt nur in der Regel-Erklärung vor)
            self.assertNotIn("| malformed_bracket |", report)
            self.assertNotIn("### malformed_bracket", report)


if __name__ == "__main__":
    unittest.main()
