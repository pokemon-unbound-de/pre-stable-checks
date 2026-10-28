# Szenario-Coverage – Pilot

Anforderung: https://github.com/pokemon-unbound-de/pokemon-unbound-de/issues/39#issuecomment-6474012382

`coverage_check.py` ergänzt Zielerreichung und minimale Laufbelege. Kein Ersatz für `gate_laufzeit_text.py`, `lint_width.py` oder ROM-Gegenprobe.

Privates Manifest bei echten Werten:

```json
{"schema":1,"scenario":"synthetic-menu","rom_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","expected_bp":"08001234","min_screenshots":1}
```

Laufordner: `druckerlog.txt`, `mgba.log`, Markerdatei `DONE`, `screenshots/*.png`. Die Screenshot-Unterordnerkonvention ist vorgeschlagen, noch nicht gegen den Runner bestätigt. Gezählt werden PNG-Signaturen; Bildinhalt und Dekodierbarkeit werden nicht geprüft.

Nevios synthetische Zeile `12 BP 00 0 0 08001234 30 BBFF` wird strikt geparst; sechste Spalte = erwartete BP-Adresse. Eine Adresse im gewöhnlichen Text oder Nutzdatenfeld zählt nicht. Abweichende echte Logvarianten bleiben rot, bis sie belegt und getestet sind.

Grün erfordert passenden ROM-SHA-256, Ziel-BP, DONE, Screenshot-Mindestzahl und beide nichtleeren Logs ohne erkannten Fatal-Marker. Muster: fatal, panic, segmentation fault, assertion failed, Python-Traceback-Kopf. Konservative Pilotregel; echte Marker und harmlose Erwähnungen müssen kalibriert werden.

    python3 coverage_check.py --manifest /privat/szenario.json --rom /privat/build.gba --run-dir /privat/frischer-lauf

Exitcodes: 0 = Coverage-Belege vollständig, 2 = rot, 1 = Eingabefehler. Ausgabe enthält Gründe/Summen, keine Textlogs, ROM-Daten oder Zieladressen. Szenario-ID passend zum Ausgabeweg wählen. Echte Manifeste bleiben privat.

## Integrationsgrenze

Jedes Szenario benötigt einen frischen getrennten Laufordner. Der Checker allein kann nicht beweisen, dass DONE, Logs und Screenshots zusammengehören oder dass die angegebene ROM tatsächlich gestartet wurde. Der Runner muss Lauf-ID und gestarteten ROM-Hash binden und Altartefakte ausschließen. Kein automatischer Eingriff in die Pipeline; Integration erst nach Nevio-Abnahme. Kein Release-Gate allein aus diesen Belegen.

## Reproduktion

    python3 -m unittest discover -s tests -v
    python3 benchmark_coverage.py

11 Coverage-Tests mit mehreren Randfällen plus 9 vorhandene Report-Tests. Der Benchmark nutzt 1 gültigen und 5 ungültige synthetische Läufe. Die vereinfachte Regel „Text vorhanden“ illustriert nur den beschriebenen Fehler; sie ist nicht Nevios tatsächlicher Gate-Code. Vorher/Nachher am echten Runner bleibt offen.

Nachgehärtet: leere/Whitespace-Logs sind rot; doppelte JSON-Manifest-Schlüssel werden als Eingabefehler abgelehnt, statt still einen Wert zu überschreiben.
