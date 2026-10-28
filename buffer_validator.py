#!/usr/bin/env python3
"""
Buffer-Validator
================
Format-/Buffer-Validator fuer das EN/DE-Uebersetzungskorpus
(Pokemon Unbound DE) — prueft, ob Spieltexte **formatgueltig** sind und
in bekannte Buffer-Limits passen. Ziel: der Pflichtfehler "Text laeuft
aus dem Fenster" und kaputte Steuer-/Farb-/Puffercodes fallen VOR der
Veroeffentlichung raus (Pre-Stable -> Stable, P0-Tool-Backlog).

Pruefungen (pro Zeile, Spalten `en` und `de`):

  C1  unknown_escape      Backslash-Folge, die nicht in der
                          Escape-Grammatik des Spiels ist
                          (Referenz: BACKSLASH_CODES in lib/pcs_text.py)
  C2  quote_imbalance     kaputte Zitat-Paarung: \\qc ohne Oeffnung oder
                          ungeschlossenes Zitat. Gueltige Paare:
                          (\\qo,\\qc) und (\\qo,\\qo) — letzteres kommt
                          im Korpus vor (EN-Original + DE) und ist
                          gueltig (Spiel laeuft fehlerfrei).
  C3  malformed_bracket   [#..] / [..] Code in ungueltiger Form
  C4  fc_odd_shape        FC-Code in 10-Hex-Form (vermutet: zwei
                          FC-Codes in einer Klammer, z. B.
                          [#FC134BFC0600] = [FC134B][FC0600];
                          Byte-Stream korrekt, Spiel laeuft -> Review)
  B1  byte_overflow       Vorlagen-Zeile: de_kurz_vorschlag > max_bytes
                          (GBA-PCS-Bytes, 1 Byte/Zeichen)
  B2  pixel_over          zeilenweise Pixelbreite > --max-pixels
                          (nur mit Flag; sonst nur Aggregat-Statistik)

Kalibrierung (Korpus v0.1.7.2, 17.188 Zeilen, Spiel laeuft fehlerfrei):
- Escape-Set = BACKSLASH_CODES der Referenz (16 x 2-Zeiger + 10 x
  1-Zeiger). Sämtliche im Korpus vorkommenden Escapes sind bekannt;
  die scheinbar seltenen Formen (\\Po, \\Ke, \\Bl, \\Lo, \\Ck, \\mn,
  \\r, \\<, \\>, \\+) sind gueltige Escapes (Name-/Steuer-Codes).
- Klammer-Codes: [#FC + 2/4/6/8 Hex], [#FDxx], [#F7xx]/[#F8xx]/[#F9xx]
  (auch ohne Argument), generische [#XX] (genau 2 Hex, z. B. [#0A]
  Menütaste, [#B9] Namensplatz, [#FA] Steuerbyte).
- Ergebnis am Kalibrierungs-Korpus: 5 Befunde (1 x C3, 4 x C4),
  d. h. das Korpus ist formatgueltig.

Wichtig:
- **Kein** automatisches Aenderen — nur Befunde + Reproduzierbarkeit.
- Die GBA-PCS-Metriken (Zeichentabelle, Glyph-Breiten, 0xFD = 54 px)
  und die Escape-Grammatik sind portiert aus Simopich/unbound-translator
  (MIT; sFontNormalLatinGlyphWidths aus pret/pokefirered src/text.c),
  Stand main @ 2026-10-28. Port byte-identisch verifiziert.
- Code ist public-safe: keine Spieltexte im Code; Korpus/Vorlagen
  werden per Pfad uebergeben.

Nutzung:
    python3 buffer_validator.py \\
        --korpus texte_v0.1.7.2.csv \\
        --vorlagen vorlagen/item_kurzformen.csv \\
        --out-dir format/
    (optional: --max-pixels 200  B2-Pruefung aktivieren)
"""

import argparse
import csv
import os
import re
import sys

# ---------------------------------------------------------------------------
# GBA-PCS-Metriken (portiert aus Simopich/unbound-translator, MIT —
# siehe Modul-Doku; identisch mit vorlagen_ergaenzen.py in namens-analyse)
# ---------------------------------------------------------------------------

# sFontNormalLatinGlyphWidths: Glyph-Vorschub in Pixeln (inkl. Spacing),
# Index = PCS-Byte, FireRed-Normal-Latin-Font.
NORMAL_GLYPH_WIDTHS = (
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    8, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 8, 6, 6, 6, 6, 6, 6, 9, 8, 8, 6,
    6, 6, 6, 6, 10, 8, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 8, 8, 8, 8, 8, 8, 4, 6, 8, 5, 5, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 12, 12, 12, 12, 6, 6, 6,
    6, 6, 6, 6, 8, 8, 8, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    8, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 6, 5,
    6, 6, 6, 3, 3, 6, 6, 8, 5, 9, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 6, 6, 4, 6, 5,
    5, 6, 5, 6, 6, 6, 5, 5, 5, 6, 6, 6, 6, 6, 6, 8,
    5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
)

# Referenzbreite des 0xFD-Textpuffers in Pixeln (nur Doku; B2-Default
# ist bewusst AUS — Bildschirm-Limits je Screen/Buffer unterscheiden sich).
RUNTIME_BUFFER_WIDTH = 54

# PCS-Byte -> Zeichen (Bereiche + Overrides aus lib/pcs_text.py,
# Einzelzeichen; Steuer-Makros sind keine Klartext-Zeichen).
_PCS_CHAR_RANGES = [
    (0x00, " \u00c0\u00c1\u00c2\u00c7\u00c8\u00c9\u00ca\u00cb\u00cc"),
    (0x0B, "\u00ce\u00cf\u00d2\u00d3\u00d4"),
    (0x10, "\u0152\u00d9\u00da\u00db\u00d1\u00df\u00e0\u00e1"),
    (0x19, "\u00e7\u00e8\u00e9\u00ea\u00eb\u00ec"),
    (0x20, "\u00ee\u00ef\u00f2\u00f3\u00f4\u0153\u00f9\u00fa\u00fb\u00f1\u00ba\u00aa"),
    (0x5A, "\u00cd%()"),
    (0xA1, "0123456789"),
    (0xAB, "!?.-\u2027"),
    (0xB7, "$,*/"),
    (0xBB, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    (0xD5, "abcdefghijklmnopqrstuvwxyz"),
    (0xF0, ":\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc"),
]
_PCS_CHAR_OVERRIDES = {
    0x2D: "&", 0x35: "=", 0x36: ";", 0x51: "\u00bf", 0x52: "\u00a1",
    0x68: "\u00e2", 0x6F: "\u00ed", 0xB3: "\u2018", 0xB4: "\u2019",
}
_PCS_TO_CHAR = {}
for _start, _chars in _PCS_CHAR_RANGES:
    for _i, _ch in enumerate(_chars):
        _PCS_TO_CHAR[_start + _i] = _ch
_PCS_TO_CHAR.update(_PCS_CHAR_OVERRIDES)

CHAR_TO_PCS = {ch: b for b, ch in _PCS_TO_CHAR.items()}
CHAR_TO_PCS["'"] = 0xB4


def pcs_len(s: str) -> int:
    """Laenge in GBA-PCS-Bytes: 1 Byte pro Zeichen (256er-Zeichensatz).

    Umlaute (a/o/u-diaeresis, ss-Zeichen, AE/OE/UE-diaeresis) sind
    1 Byte wie lateinische Zeichen — im Gegensatz zu UTF-8 (2 Byte).
    """
    for ch in s:
        if ch not in CHAR_TO_PCS:
            raise ValueError(f"Zeichen {ch!r} nicht im PCS-Zeichensatz: {s!r}")
    return len(s)


# ---------------------------------------------------------------------------
# Steuer-/Markierungscodes (Korpus-Format der Dialogwerkstatt)
# ---------------------------------------------------------------------------

# Escape-Grammatik: portiert aus BACKSLASH_CODES + CONTROL_TOKEN_RE in
# lib/pcs_text.py (Simopich/unbound-translator, MIT) — der
# grammatikalische Referenzstandard des Spiels. Kalibrierung am Korpus
# v0.1.7.2: alle vorkommenden Escapes sind bekannt (C1 liefert dort 0).
#
# 2-Zeiger (Reihenfolge + Lookahead wie in der Referenz):
#   \pk \Po  (Name-Logos)      \mn \Ke \Bl \Lo \Ck \Lv (weitere Name-Codes)
#   \qo \qc  (Zitat an/aus)    \sm \sf  (Schriftmodus)
#   \au \ad \ar \al  (Pfeile hoch/runter/rechts/links)
# 1-Zeiger:  \n \l \p \e \d \r \. \< \> \+
ESCAPES_2 = ("pk", "Po", "mn", "Ke", "Bl", "Lo", "Ck", "Lv",
             "qo", "qc", "sm", "sf", "au", "ad", "al", "ar")
ESCAPES_1 = frozenset(["n", "l", "p", "e", "d", "r", ".", "<", ">", "+"])

# Tokenisierungs-Regex (gleiche Alternativen-Reihenfolge + Lookaheads
# wie CONTROL_TOKEN_RE in der Referenz, nur die Escape-Gruppe).
ESCAPE_RE = re.compile(
    r"\\(?:pk(?![A-Za-z])|Po(?![A-Za-z])|mn|Ke|Bl|Lo|Ck|Lv|qo|qc|sm|sf|"
    r"au|ad|al|ar|n|l|p|e|d|r|\+|<|>|\.)"
)

# Zitat-Escapes (Referenz: \qo = 0xB1, \qc = 0xB2).
QUOTE_RE = re.compile(r"\\(qo|qc)")

# Klammer-Codes: Inhalt wird allgemein erfasst (auch Fehlformen); die
# Gueiltigkeit prueft _bracket_ok (C3), die Argument-Laenge _fc_odd (C4).
BRACKET_RE = re.compile(r"\[(#[0-9A-Za-z]+|[A-Za-z][A-Za-z0-9]*)\]")

_HEX = frozenset("0123456789ABCDEFabcdef")


def _is_hex(s: str) -> bool:
    return bool(s) and all(c in _HEX for c in s)


# Makronamen (aus lib/pcs_text.py: FD_MACROS + F9_MACROS)
MACRO_NAMES = frozenset(
    ("player", "buffer1", "buffer2", "buffer3", "kun", "rival",
     "up", "down", "left", "right"))

# Gueltige FC-Argument-Laengen (Anzahl Hex-Ziffern hinter 'FC'):
#   2/4/6: ueblich im Korpus (5825/4870/10 Vorkommen)
#   8:     z. B. FC04 mit 3 Argumenten ([#FC040D0E0F], 2x im Korpus)
#   10:    4x im Korpus — Konkatenation zweier FC-Codes in einer Klammer
#          (z. B. [#FC134BFC0600] = [FC134B][FC0600]); der Byte-Stream
#          ist korrekt und das Spiel laeuft, daher nur Review (C4),
#          kein Formatfehler (C3).
FC_HEX_OK = (2, 4, 6, 8)
FC_HEX_ODD = 10


def _fc_hex_len(core: str):
    """Anzahl Hex-Ziffern hinter 'FC'; None falls core kein FC-Code ist."""
    if not core.startswith("FC"):
        return None
    rest = core[2:]
    return len(rest) if rest and _is_hex(rest) else None


def _bracket_ok(tok: str) -> bool:
    """tok = Inhalt ohne Klammern, z. B. '#FC0106', 'FD0F', 'player'.

    Gueltige Formen (am Korpus v0.1.7.2 + Referenz kalibriert):
      #FCxx / #FCxxxx / #FCxxxxxx / #FCxxxxxxxx  (2/4/6/8 Hex)
      #FDxx  (Puffer-Makro, 2 Hex)
      #F7xx / #F8xx / #F9xx  (Makro-Präfix + 2 Hex) — auch ohne Argument
      #XX  (generische 2-Hex-Byte: [#0A] Menütaste, [#B9] Namensplatz,
            [#30]/[#3C], [#FA] Steuerbyte)
      (ohne #: [FCxx]..., [FDxx], Makronamen [player], [buffer1]...)
    """
    core = tok[1:] if tok.startswith("#") else tok
    n = _fc_hex_len(core)
    if n is not None:
        return n in FC_HEX_OK
    if core.startswith("FD"):
        return len(core) == 4 and _is_hex(core[2:])
    if core[:2] in ("F7", "F8", "F9"):
        return len(core) == 2 or (len(core) == 4 and _is_hex(core[2:]))
    if tok.startswith("#") and len(core) == 2:
        return _is_hex(core) and core not in ("FC", "FD")
    return core in MACRO_NAMES


def _fc_odd(core: str) -> bool:
    """True, wenn ein FC-Code die ungewoehnliche 10-Hex-Form hat (C4)."""
    return _fc_hex_len(core) == FC_HEX_ODD


def c1_unknown_escapes(text: str):
    """C1: Details aller Backslash-Positionen, an denen kein bekannter
    Escape folgt (Referenz-Grammatik)."""
    details = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "\\":
            i += 1
            continue
        m = ESCAPE_RE.match(text, i)
        if m:
            i = m.end()
            continue
        nxt = text[i + 1] if i + 1 < n else None
        details.append("\\" + nxt if nxt is not None
                       else "Backslash am Zeilenende")
        i += 1
    return details


def c2_quote_findings(text: str):
    """C2: Zitat-Balance (\\qo/\\qc) durch Paar-Abgleich.

    Gueltige Zitat-Paare (am Korpus + EN-Original kalibriert):
      (\\qo, \\qc)  Oeffnung + schliessendes \\qc
      (\\qo, \\qo)  Oeffnung + schliessendes \\qo — kommt 16x in 7
                    Zeilen vor (u. a. im EN-Original) und ist gueltig;
                    das Spiel laeuft mit beiden Formen fehlerfrei.
    Befunde: \\qc ohne vorangehende Oeffnung / ungeschlossenes Zitat.
    """
    n_open = n_close = 0
    expect_open = True
    for m in QUOTE_RE.finditer(text):
        ev = m.group(1)
        if expect_open:
            if ev != "qo":
                return [f"\\qc ohne Oeffnung (\\qo={n_open} \\qc={n_close + 1})"]
            n_open += 1
            expect_open = False
        else:
            n_close += 1
            expect_open = True
    if not expect_open:
        return [f"ungeschlossenes Zitat (\\qo={n_open} \\qc={n_close}, "
                f"ungerade Anzahl Zitat-Events)"]
    return []


def check_text(text: str):
    """C1–C4-Befunde einer Textspalte: List[(code, detail)]."""
    findings = []
    for d in c1_unknown_escapes(text):
        findings.append(("unknown_escape", d))
    for d in c2_quote_findings(text):
        findings.append(("quote_imbalance", d))
    for m in BRACKET_RE.finditer(text):
        tok = m.group(1)
        core = tok[1:] if tok.startswith("#") else tok
        if _fc_odd(core):
            findings.append(("fc_odd_shape",
                             f"[{tok}] ({len(core) - 2} Hex — vermutlich "
                             f"mehrere FC-Codes in einer Klammer)"))
        elif not _bracket_ok(tok):
            findings.append(("malformed_bracket", f"[{tok}]"))
    return findings


def line_pixel_widths(text: str):
    """Pixelbreite je Zeile (Referenz-Semantik text_pixel_width):

    0xFF stop, 0xFC + Argumente skip (0 px), 0xFD = +54 px,
    0xFA/FB/FE = 0, sonst Glyph-Breite. Zeilen-Grenzen: \\n, \\p, \\l.
    Klammer-Codes: FD = +54 px, FC/FA/FB/FE = 0 px, gueltige 2-Hex-
    Bytes und F7/F8/F9-Makros = Glyph-Breite des PCS-Bytes; Zeichen
    außerhalb des PCS-Satzes zaehlen konservativ 6 px.
    """
    widths = []
    for line in re.split(r"\\[npl]", text):
        width = 0
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            if ch == "\\":
                m = ESCAPE_RE.match(line, i)
                if m:
                    i = m.end()
                    continue
                i += 2 if i + 1 < n else 1  # unbekannt: Backslash + 1 Zeichen
                continue
            if ch == "[":
                j = line.find("]", i)
                if j < 0:
                    i += 1
                    continue
                core = line[i + 1:j]
                core = core[1:] if core.startswith("#") else core
                if core.startswith("FD"):
                    width += RUNTIME_BUFFER_WIDTH  # 0xFD = +54 px
                elif (core.startswith("FC") or core in ("FA", "FB", "FE")
                      or _fc_odd(core)):
                    pass  # Steuer-/Konkatenations-Codes: 0 px
                elif len(core) == 2 and _is_hex(core):
                    width += NORMAL_GLYPH_WIDTHS[int(core, 16)]
                elif core[:2] in ("F7", "F8", "F9") and len(core) in (2, 4):
                    width += NORMAL_GLYPH_WIDTHS[int(core[:2], 16)]
                i = j + 1
                continue
            b = CHAR_TO_PCS.get(ch)
            width += NORMAL_GLYPH_WIDTHS[b] if b is not None else 6
            i += 1
        widths.append(width)
    return widths or [0]


# ---------------------------------------------------------------------------
# Prueflauf
# ---------------------------------------------------------------------------

CALIBRATION_NOTES = (
    "## Gueltige Formen (Kalibrierung: Korpus v0.1.7.2 + Referenz)",
    "",
    "- Escapes: 1-Zeiger `\\n \\l \\p \\e \\d \\r \\. \\< \\> \\+`; "
    "2-Zeiger `\\pk \\Po \\mn \\Ke \\Bl \\Lo \\Ck \\Lv \\qo \\qc "
    "\\sm \\sf \\au \\ad \\ar \\al`",
    "- Klammer-Codes: `[#FCxx/xxxx/xxxxxx/xxxxxxxx]`, `[#FDxx]`, "
    "`[#F7xx]/[#F8xx]/[#F9xx]` (auch ohne Argument), generische "
    "`[#XX]` (genau 2 Hex)",
    "- Zitate: Paare `(\\qo,\\qc)` und `(\\qo,\\qo)` (\\qo schliesst "
    "Zitate ebenfalls — 16x im Korpus, EN-Original + DE, gueltig)",
    "- FC in 10-Hex-Form = `fc_odd_shape` (Review), kein Formatfehler",
    "- B1-Pruefung nur fuer die 21 Zeilen von item_kurzformen.csv "
    "(bekannte Buffer-Limits; Template-Adressen sind ROM-Adressen, "
    "keine Korpus-IDs)",
)


def run(korpus_pfad, vorlagen_pfad, out_dir, max_pixels=None):
    findings = []  # (id, kategorie, ort, spalte, code, detail)

    rows = []
    with open(korpus_pfad, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            rows.append(row)
    print(f"-> {len(rows)} Korpus-Zeilen", file=sys.stderr)

    pixel_all = []
    for row in rows:
        rid = (row.get("id") or "").strip()
        kate = (row.get("kategorie") or "").strip()
        ort = (row.get("ort") or "").strip()
        for spalte in ("en", "de"):
            text = row.get(spalte) or ""
            for code, detail in check_text(text):
                findings.append((rid, kate, ort, spalte, code, detail))
            widths = line_pixel_widths(text)
            pixel_all.extend(widths)
            if max_pixels is not None:
                over = [w for w in widths if w > max_pixels]
                if over:
                    findings.append((rid, kate, ort, spalte, "pixel_over",
                                     f"max {max(over)} px > {max_pixels} px"))

    # B1: Vorlagen-Zeilen (bekannte Buffer-Limits, GBA-PCS-Bytes)
    n_vorlagen = 0
    if vorlagen_pfad:
        with open(vorlagen_pfad, encoding="utf-8", newline="") as fh:
            for vrow in csv.DictReader(fh, delimiter=";"):
                n_vorlagen += 1
                kurz = (vrow.get("de_kurz_vorschlag") or "").strip()
                try:
                    max_bytes = int((vrow.get("max_bytes") or "0").strip())
                except ValueError:
                    continue
                try:
                    blen = pcs_len(kurz)
                except ValueError as e:
                    findings.append((vrow.get("id", "?"), "vorlage", "",
                                     "de_kurz", "pcs_unmapped", str(e)))
                    continue
                if blen > max_bytes:
                    findings.append((vrow.get("id", "?"), "vorlage", "",
                                     "de_kurz", "byte_overflow",
                                     f"{blen} > {max_bytes} PCS-Bytes"))
        print(f"-> {n_vorlagen} Vorlagen-Zeilen (B1-Pruefung)",
              file=sys.stderr)

    # Output-CSV (privat: IDs + Befunde, keine Textinhalte)
    os.makedirs(out_dir, exist_ok=True)
    csv_pfad = os.path.join(out_dir, "format_check.csv")
    with open(csv_pfad, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["id", "kategorie", "ort", "spalte", "code", "detail"])
        w.writerows(findings)
    print(f"-> {csv_pfad} ({len(findings)} Befunde)", file=sys.stderr)

    # Aggregat-Report (ohne Spieltexte)
    by_code = {}
    for f in findings:
        by_code.setdefault(f[4], []).append(f)
    pixel_all.sort()
    pct = lambda q: (pixel_all[int(len(pixel_all) * q)]
                     if pixel_all else 0)
    lines = [
        "# Format-/Buffer-Validator: Report",
        "",
        f"- Korpus-Zeilen: {len(rows)}"
        + (f", Vorlagen-Zeilen: {n_vorlagen}" if vorlagen_pfad else ""),
        f"- Befunde gesamt: {len(findings)}",
        "",
        "| Code | Anzahl | Bedeutung |",
        "|---|---|---|",
    ]
    meanings = {
        "unknown_escape": "C1: Backslash-Folge nicht in der Escape-"
                          "Grammatik (Referenz: BACKSLASH_CODES)",
        "quote_imbalance": "C2: kaputte Zitat-Paarung (\\qc ohne "
                           "Oeffnung / ungeschlossenes Zitat)",
        "malformed_bracket": "C3: [#..]/[..] Code in ungueltiger Form",
        "fc_odd_shape": "C4: FC-Code in 10-Hex-Form (vermutet: mehrere "
                        "FC-Codes in einer Klammer; zur Pruefung)",
        "byte_overflow": "B1: Kurzform > max_bytes (GBA-PCS-Bytes)",
        "pixel_over": "B2: Zeilen-Pixelbreite > Schwelle",
        "pcs_unmapped": "B1: Zeichen auerhalb des PCS-Satzes",
    }
    for code in sorted(by_code):
        lines.append(f"| {code} | {len(by_code[code])} | "
                     f"{meanings.get(code, '')} |")
    lines += [
        "",
        *CALIBRATION_NOTES,
        "",
        "## Pixelbreiten (FireRed-Normalfont, pro Textzeile; 0xFD = 54 px)",
        "",
        f"- p50: {pct(0.50)} px | p90: {pct(0.90)} px | p99: {pct(0.99)} px"
        f" | max: {pixel_all[-1] if pixel_all else 0} px",
        f"- Referenz 0xFD-Textpuffer: {RUNTIME_BUFFER_WIDTH} px",
        "- B2-Pruefung: " + (
            f"aktiv (--max-pixels {max_pixels})"
            if max_pixels is not None
            else "aus (nur Statistik; Limits je Screen/Buffer "
                 "unterscheiden sich)"),
        "",
        "## Befund-Beispiele (IDs ohne Textinhalte)",
        "",
    ]
    for code in sorted(by_code):
        lines.append(f"### {code} ({len(by_code[code])})")
        for f in by_code[code][:10]:
            lines.append(f"- `{f[0]}` ({f[3]}): {f[5]}")
        if len(by_code[code]) > 10:
            lines.append(f"- ... ({len(by_code[code]) - 10} weitere in "
                         f"format_check.csv)")
        lines.append("")
    if not by_code:
        lines.append("(keine Befunde — Korpus formatgueltig)")
        lines.append("")
    report_pfad = os.path.join(out_dir, "format_report.md")
    with open(report_pfad, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"-> {report_pfad}", file=sys.stderr)

    print("=== ZUSAMMENFASSUNG ===", file=sys.stderr)
    print(f"Zeilen: {len(rows)} | Befunde: {len(findings)}"
          + (f" (B2 aktiv: --max-pixels {max_pixels})"
             if max_pixels is not None else ""), file=sys.stderr)
    return 0


def main():
    p = argparse.ArgumentParser(description="Format-/Buffer-Validator")
    p.add_argument("--korpus", required=True,
                   help="Korpus-CSV (;-getrennt: id;en;de;kategorie;ort)")
    p.add_argument("--vorlagen", default=None,
                   help="item_kurzformen.csv (B1: max_bytes in PCS-Bytes)")
    p.add_argument("--out-dir", default="format")
    p.add_argument("--max-pixels", type=int, default=None,
                   help="B2-Schwelle: Zeilen-Pixelbreite > N px melden "
                        "(Default: aus, nur Statistik)")
    args = p.parse_args()
    return run(args.korpus, args.vorlagen, args.out_dir, args.max_pixels)


if __name__ == "__main__":
    sys.exit(main())
