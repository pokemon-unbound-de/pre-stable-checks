# Szenario-Coverage – Pilot

Anforderung: https://github.com/pokemon-unbound-de/pokemon-unbound-de/issues/39#issuecomment-6474012382

`coverage_check.py` ergänzt Zielerreichung und minimale Laufbelege. Kein Ersatz für `gate_laufzeit_text.py`, `lint_width.py` oder ROM-Gegenprobe.

Privates Manifest bei echten Werten:

```json
{"schema":1,"scenario":"synthetic-menu","rom_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","expected_bp":"08001234","min_screenshots":1}
```

Laufordner: `druckerlog.txt`, `mgba.log`, Markerdatei `DONE`, `*.png` direkt im Laufordner, wie von Nevio am echten Runner bestätigt. Es wird nicht rekursiv gesucht; `_duplikate/` und andere Unterordner werden nicht gezählt. Gezählt werden Dateien mit bestandener PNG-Kernstruktur-/CRC-Prüfung; ungültige Root-PNGs führen zu `screenshots_invalid` und Rot, auch wenn genügend andere Bilder vorhanden sind. `screenshots` nennt die bestandenen Dateien, `invalid_screenshots` die abgelehnten. Bildinhalt und vollständige Dekodierbarkeit werden nicht geprüft; Details in `PNG_EVIDENCE.md`.

Nevios synthetische Zeile `12 BP 00 0 0 08001234 30 BBFF` wird strikt geparst;
sechste Spalte = BP-Adresse. Die neue neunte Spalte (Fensterhöhe in Kacheln,
z. B. `... BBFF 4`) ist optional. Breite und Höhe sind Dezimalzahlen.
Andere Zusatzspalten oder unvollständige Hexbytes gelten nicht als Zielbeleg.

Für Msgbox-Läufe kann das private Manifest zusätzlich oder alternativ einen
konkreten Textbeleg aus einem ausdrücklich benannten RAM-Puffer anfordern:

```json
{"schema":1,"scenario":"synthetic-buffer","rom_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","expected_buffer_bp":"02021D07","expected_hex":"AABBCCDD","min_screenshots":1}
```

`expected_hex` umfasst 4 bis 4096 vollständige Bytes ohne Leerzeichen. Nur eine
Bytefolge im Hexfeld einer BP-Zeile mit exakt dieser RAM-Adresse zählt; Textzeilen,
andere Puffer, ROM-Adressen und Treffer zwischen Hex-Halbbytes zählen nicht.
Vorhandenes `expected_bp` bleibt als alternativer Adressbeleg möglich.
`target_evidence` nennt `bp_address`, `buffer_hex` oder `missing`, ohne private
Adressen/Bytes auszugeben. Die Signatur muss vom Szenario-Owner ausreichend
eindeutig gewählt und am gestarteten Build gebunden werden. Ein Pufferbeleg
beweist beobachtete Bytes, keine Herkunft von einem bestimmten ROM-Zeiger und
keine Rendering-/Szenenfreigabe. Diese Anpassung folgt Issue2/6547484231;
der neue echte G2c-Beweislauf ist projektseitig nachzuprüfen.

Grün erfordert passenden ROM-SHA-256, Zielbeleg (BP-Adresse oder explizite RAM-Bytefolge), DONE, Screenshot-Mindestzahl, keine strukturell ungültigen Root-PNGs und beide nichtleeren Logs ohne erkannten Fatal-Marker. Muster: fatal, panic, segmentation fault, assertion failed, Python-Traceback-Kopf, `Illegal opcode`, `Stub software interrupt`. Vorhandene Runner-Befunde `ABSTURZ.txt` oder `FREEZE.txt` führen ebenfalls zu rot, auch bei leerem Dateiinhalt. Konservative Pilotregel; echte Marker und harmlose Erwähnungen müssen kalibriert werden.

    python3 coverage_check.py --manifest /privat/szenario.json --rom /privat/build.gba --run-dir /privat/frischer-lauf

Exitcodes: 0 = Coverage-Belege vollständig, 2 = rot, 1 = Eingabefehler. Ausgabe enthält Gründe/Summen, keine Textlogs, ROM-Daten oder Zieladressen. Szenario-ID passend zum Ausgabeweg wählen. Echte Manifeste bleiben privat.

## Integrationsgrenze

Jedes Szenario benötigt einen frischen getrennten Laufordner. Der Checker allein kann nicht beweisen, dass DONE, Logs und Screenshots zusammengehören oder dass die angegebene ROM tatsächlich gestartet wurde. Der Runner muss Lauf-ID und gestarteten ROM-Hash binden und Altartefakte ausschließen. Kein automatischer Eingriff in die Pipeline; Integration erst nach Nevio-Abnahme. Kein Release-Gate allein aus diesen Belegen.

## Reproduktion

    python3 -m unittest discover -s tests -v
    python3 benchmark_coverage.py

49 Tool-Tests (28 Coverage, 8 Binding, 2 Replay, 11 PNG-Struktur), ausschließlich im isolierten Pilot. Die frühere lokale Report-Prototyp-Suite gehört nicht zu diesem PR. Der Benchmark nutzt 1 gültigen und 5 ungültige synthetische Läufe. Die vereinfachte Regel „Text vorhanden“ illustriert nur den beschriebenen Fehler; sie ist nicht Nevios tatsächlicher Gate-Code. Vorher/Nachher am echten Runner bleibt offen.

Nachgehärtet: leere/Whitespace-Logs sind rot; doppelte JSON-Manifest-Schlüssel werden als Eingabefehler abgelehnt, statt still einen Wert zu überschreiben.

Anpassung nach Nevios echter Gegenprobe (Kommentar 6474525076): Root-PNGs,
keine Unterordner-Duplikate, dezimale Fensterbreiten, beide mGBA-Absturzmarker
und Runner-Befunddateien. Die erneute Gegenprobe am vorhandenen echten Lauf
muss projektseitig erfolgen, da diese Laufartefakte hier nicht verfügbar sind.

## Optionaler nächster Schritt

`--require-binding --run-id <aktuelle-runner-id>` aktiviert den vorgeschlagenen
Abgleich von Lauf-ID, Szenario, gestartetem ROM-Hash und Artefakt-Hashes in
`run_evidence.json`. Ohne diese Optionen bleibt `binding: unchecked` explizit
sichtbar. `RUN_BINDING.md` beschreibt die vom Runner zu erfüllenden Bedingungen.
Das ist ein vorbereiteter Vertrag, keine bereits erfolgte Runner-Integration.

## Dateibasierter Abnahme-Replay

    python3 replay_checks.py

Erzeugt vorübergehend ausschließlich synthetische Dateien (keine Spiel-ROM,
keine Saves, keine echten Textlogs) und prüft 14 Fälle durch denselben
CLI-Einstiegspunkt: 1 erfolgreicher gebundener Lauf und 13 Negativfälle,
einschließlich veralteter Lauf-ID, geändertem Bild, falscher ROM, fehlendem
Ziel/Abschluss, Root-PNGs vs. Duplikaten und Runner-Absturzmarkern. Ein zusätzlicher Fall enthält17 auf den Dateikopf abgeschnittene Bilder mit neu berechneten, passenden Beleg-Hashes: Binding bleibt matched, Coverage wird trotzdem rot. Die übrigen
PNG-Fixtures sind vollständige generierte 1×1-Bilder. JSON nennt Fall-ID,
Soll-/Ist-Exitcode und Prüfzeit. Exit 0 nur, wenn jeder Fall einschließlich
seines erwarteten Grundcodes stimmt. Dateien werden danach entfernt.

Die Laufzeiten umfassen den In-Prozess-CLI-Check und Datei-IO, nicht die
Fixture-Erstellung, einen Emulator oder neue Prozessstarts. Das ist eine
Abnahmehilfe, kein Nachweis für Laufzeit oder Abdeckung des echten Spiels.
