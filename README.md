# pre-stable-checks

Tools fuer den Stable-Uebergang der Pokémon-Unbound-DE-Übersetzung
(Pre-Stable → Stable). Zwei unabhängige Python-Tools, **nur
Python-Standardbibliothek**, deterministisch, ohne Netzwerkzugriff:

| Tool | Datei | Zweck |
|---|---|---|
| Format-/Buffer-Validator | [`buffer_validator.py`](buffer_validator.py) | Prüft, dass Spieltexte **formatgültig** sind und in bekannte Buffer-Limits passen (Steuer-/Farb-/Puffer-Codes, GBA-PCS-Byte-Limits, Pixelbreite) |
| Stable-Fenster-Tracker | [`stable_fenster.py`](stable_fenster.py) | Misst das Stable-Kriterium „14 Tage ohne Pflichtfehler“ als reproduzierbare Zahl statt Bauchgefühl |

Beide Tools **ändern nichts** — sie erzeugen nur Befunde, die sich
reproduzieren lassen.

---

## Format-/Buffer-Validator

Prüft pro Zeile die Spalten `en` und `de` eines Korpus-CSVs
(`;`-getrennt, Spalten `id;en;de;kategorie;ort`):

| Code | Prüfung |
|---|---|
| `unknown_escape` (C1) | Unbekannte Backslash-Folge in DE nach der lokalen Referenz-Grammatik |
| `reference_unknown_escape` | Unbekannte Escape-Notation im EN-Original: informativ, kein DE-Formatfehler und keine Encoding-Freigabe |
| `quote_imbalance` (C2) | Kaputte Zitat-Paarung: `\qc` ohne Oeffnung oder ungeschlossenes Zitat. Gültige Paare: `(\qo,\qc)` und `(\qo,\qo)` |
| `malformed_bracket` (C3) | `[#..]`-Rohbytefolge in ungültiger Form (ungerade Hex oder nicht-hex; **gerade Hex = gültig** nach Encoder-Regel) |
| `fc_odd_shape` (C4) | Kompakte FC-Notation ohne `#` mit 10 Hex: informativ. Gerade `[#…]`-Rohbytefolgen, einschließlich kombinierter FC-Folgen, erzeugen keinen solchen Hinweis. |
| `byte_overflow` (B1) | Vorlagen-Zeile: `de_kurz_vorschlag` > `max_bytes` (GBA-PCS-Bytes, 1 Byte/Zeichen) |
| `pixel_over` (B2) | Zeilen-Pixelbreite > `--max-pixels` (nur mit Flag; Default: nur Aggregat-Statistik, da Bildschirm-Limits je Screen/Buffer unterschiedlich sind) |

### Nutzung

Anpassung nach Nevios Rückmeldung in Datenrepo Issue #2/6547484231:
zusammengefasste Rohbytefolgen wie `[#FC134BFC0600]` sind syntaktisch gültig.
Der Prüfer leitet daraus keine FC-Handler-/Parametersemantik ab. EN-Originale
werden nicht verändert; unbekannte Quellnotation bleibt gesondert sichtbar.
43 Format-Tests einschließlich ungültiger Rohbytefolgen und getrennter
EN-/DE-Beurteilung bestehen. Historische Kalibrierungszahlen unten beziehen
sich auf den damaligen Prüferstand.

```bash
python3 buffer_validator.py \
    --korpus texte_v0.1.7.2.csv \
    --vorlagen item_kurzformen.csv \
    --out-dir format/ \
    [--max-pixels 200]
```

Ergebnis: `format/format_check.csv` (Befunde: ID + Code + Detail,
ohne Textinhalte) und `format/format_report.md` (Aggregat-Report).

### Kalibrierung

Am Korpus **v0.1.7.2** (17.188 Zeilen) kalibriert — das Spiel läuft
fehlerfrei, daher gilt: was im Korpus und im EN-Original vorkommt,
ist gültig. Ergebnis am Kalibrierungs-Korpus nach der QA-Korrektur
(2026-10-28): **5 Befunde** (1× C1 in der EN-Spalte, 4× C4
informativ); **C3 = 0** (der ehemalige `[#FEFD02FC09]`-Befund war
Falschpositiv nach der Encoder-Regel). Das Formatgültigkeits-Urteil
gelten **nur innerhalb der Prüf-Abgrenzung** (s. u.), nicht als
Gesamturteil über das gesamte Spiel.

Gültige Formen (Auszug; Details im Modul-Docstring):

- **Escapes:** 1-Zeiger `\n \l \p \e \d \r \. \< \> \+`;
  2-Zeiger `\pk \Po \mn \Ke \Bl \Lo \Ck \Lv \qo \qc \sm \sf \au \ad \ar \al`
  (Grammatik = `BACKSLASH_CODES`/`CONTROL_TOKEN_RE` der Referenz,
  inkl. Lookahead-Regeln `pk(?![A-Za-z])` / `Po(?![A-Za-z])`)
- **Klammer-Codes, `#`-Familie (Rohbytefolgen):** DIFFERENZIELLE
  REGEL gegen den echten Encoder `tools/pcs_encode.py`
  (`_RAW`-Regex `[#HH…]` + `bytes.fromhex`, verifiziert 2026-10-28):
  `#` + **gerade** Hex-Ziffern (≥ 2) = gültige Rohbytefolge
  (z. B. `[#0A]` Menütaste, `[#FA]` Steuerbyte, `[#FEFD02FC09]`);
  **ungerade** Hex oder nicht-hex = `malformed_bracket` (C3).
- **Klammer-Codes ohne `#`** (Makro-Kurzformen + Namen): `[FCxx]…`
  (2/4/6/8 Hex nach FC), `[FDxx]`, `[F7xx]/[F8xx]/[F9xx]` (auch ohne
  Argument), Makronamen `[player]`, `[buffer1]` …
- **Zitate:** `\qo` schließt Zitate ebenfalls (`\qo…\qo` kommt 16×
  im Korpus vor, u. a. im EN-Original — gültig)
- **C4** (FC + 10 Hex) = **informativ**: syntaktisch gültige
  Rohbytefolge, semantisch zu prüfen — zählt nicht gegen die
  Formatgültigkeit
- **B1-Prüfung** nur für die 21 Zeilen von `item_kurzformen.csv`
  (bekannte Buffer-Limits; die Template-Adressen dort sind
  ROM-Skript-Adressen, keine Korpus-IDs)

Bewusst **keine** strikte FC-Argument-Prüfung: Der Korpus nutzt
`[FC01]`-Kurzformen (5.000+ Zeilen), die der Spiel-Laufzeit
einwandfrei verarbeitet — eine Semantik-Prüfung würde massenhaft
Fehlalarme liefern.

### Prüf-Abgrenzung (was der Validator prüft und was nicht)

Das Formatgültigkeits-Urteil beschränkt sich bewusst auf den
geprüften Umfang und ist **kein** Gesamturteil:

- **C1/C2/C3:** alle Korpus-Zeilen, Spalten `en` und `de`.
- **B1:** nur die 21 Vorlagen-Zeilen von `item_kurzformen.csv`.
- **B2:** standardmäßig **aus** (nur Aggregat-Statistik), weil die
  Screen-Limits je Screen/Buffer unterschiedlich sind.
- **Nicht geprüft:** Laufzeit-Verhalten, echtes Screen-Layout,
  ROM-Tabellen.

Der Report enthält deshalb pro Befund die Trennung
*formatrelevant* (C1/C2/C3/B1) vs. *informativ* (C4) und ein
explizites Formatgültigkeits-Urteil innerhalb dieser Abgrenzung.

### Herkunft der Metriken

- GBA-PCS-Zeichentabelle, Glyph-Breiten
  (`sFontNormalLatinGlyphWidths`), `text_pixel_width`-Semantik
  (0xFC+Args = 0 px, 0xFD = +54 px, 0xFA/FB/FE = 0 px) und die
  Escape-Grammatik: portiert aus
  [Simopich/unbound-translator](https://github.com/Simopich/unbound-translator)
  (MIT), Stand main @ 2026-10-28; der Port wurde **byte-identisch
  gegen die Referenz verifiziert**.
- `sFontNormalLatinGlyphWidths` stammt ursprünglich aus
  pret/pokefirered (`src/text.c`).

## Stable-Fenster-Tracker

**Stable v1.0.0 gilt, wenn 14 Tage lang kein Pflichtfehler gemeldet
wurde.** Der Tracker hält das Fenster in einer manuell gepflegten
CSV (ein Eintrag pro Pflichtfehler-Meldung aus `#beta-bugs`) und
rechnet Fenster-Ende und Status aus — ohne Discord-API.

Pflichtfehler (die einzigen Stable-Blocker):
`en_rest`, `text_breite`, `grammatik`, `grafik`, `absturz`.

CSV-Format (`stable_fenster.csv`):

```
id;datum;fix_datum;typ;status;quelle
SF-001;2026-10-20;2026-10-21;en_rest;gefixt;Beta v0.1.6, Ruhmeshalle
SF-002;2026-10-28;;text_breite;offen;Beta v0.1.7, Kampfturm
```

- `datum`: Meldedatum (YYYY-MM-DD)
- `fix_datum`: Fixdatum (YYYY-MM-DD) — **Pflicht bei `gefixt`**,
  sonst leer. Das 14-Tage-Fenster läuft vom **Fixdatum**, nicht vom
  Meldedatum; es muss ≥ `datum` sein.
- `status`:
  - `offen`: offener Fehler — blockiert das Stable-Kriterium
    **vollständig** (wird unabhängig von Fenstern niemals grün;
    erst bei Änderung zu `gefixt` + fix_datum oder
    `kein_pflichtfehler` relevant)
  - `gefixt`: fixiert — Fenster läuft ab `fix_datum`
  - `kein_pflichtfehler`: False Positive, zählt nie
- `id`: aufsteigend `SF-001`, `SF-002`, … (wird bei `--add`
  automatisch vergeben)

Aussagefähigkeit: Eine fehlende, leere oder nur aus
`kein_pflichtfehler`-Zeilen bestehende CSV bedeutet **UNBESTAETIGT**
— es liegen keine Daten vor, die das Kriterium bestätigen. In diesem
Fall gibt der Tracker **keine Freigabe** (Exit 2).

Exit-Codes (maschinenlesbar):

| Exit | Bedeutung |
|---|---|
| `0` | STABLE-KRITERIUM ERFÜLLT |
| `1` | Input-Fehler (ungültige Zeilen, Schema-Mismatch) |
| `2` | nicht grün (offener Pflichtfehler / Fenster läuft / Fenster endet heute / UNBESTAETIGT) |

Grenze: Fenster-Ende = letztes `fix_datum` + 14 Tage. Am
Fenster-Endtag selbst meldet der Tracker „FENSTER ENDET HEUTE“ (Exit
2, morgen Stable-fähig); grün wird er erst ab dem Folgetag.

### Nutzung

```bash
# Fenster prüfen (Default: heutiges Datum)
python3 stable_fenster.py --csv stable_fenster.csv

# Referenz-Datum (z. B. für Reproduktion)
python3 stable_fenster.py --csv stable_fenster.csv --heute 2026-11-04

# Neue Meldung anhängen (id automatisch)
python3 stable_fenster.py --csv stable_fenster.csv \
    --add "2026-11-04;;grammatik;offen;Beta v0.1.7, Kampfturm"

# Fix dokumentieren (fix_datum im 2. Feld)
python3 stable_fenster.py --csv stable_fenster.csv \
    --add "2026-11-04;2026-11-06;grammatik;gefixt;Beta v0.1.7, Kampfturm"
```

`--add` erwartet `datum;fix_datum;typ;status;quelle`.

Ausgabe: Fenster-Ende (letztes fix_datum + 14 Tage), Status,
Aggregate je Fehler-Typ. Ungültige Zeilen (ID/Datum/fix_datum/Typ/
Status) werden gemeldet; der Exit-Code ist 1. Alt-Schema-Dateien
(ohne `fix_datum`) werden abgelehnt und die Migration angezeigt.

## Tests

Synthetische Fixtures, ohne Spieltexte:

```bash
python3 tests/test_buffer_validator.py   # 38 Tests
python3 tests/test_stable_fenster.py     # 39 Tests
```

## Public-Safety

Keine Spieltexte im Code oder in den Test-Fixtures. Korpus und
Vorlagen werden per Pfad übergeben; die Befund-Dateien enthalten
nur IDs, Codes und kurze Code-Formen — keine Textinhalte.
