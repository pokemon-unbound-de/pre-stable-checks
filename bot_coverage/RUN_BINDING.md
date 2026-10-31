# Vorschlag: Laufbelege eindeutig zuordnen

Optionaler Integrationsvertrag zur Abnahme durch den Runner-Owner. Noch nicht
im echten Runner implementiert. Der bisherige isolierte Coverage-Aufruf bleibt
verfügbar und meldet `binding: unchecked`.

## Runner-Seite

1. Vor Start eine neue Lauf-ID erzeugen und einen frischen Laufordner exklusiv
   anlegen; existierende Ordner nicht wiederverwenden. Die erwartete Lauf-ID
   in der aktuellen Runner-Ausführung halten, nicht aus alten Dateien lesen.
2. Genau die gestartete ROM identifizieren. Ihr Hash muss zu den tatsächlich
   geladenen Bytes gehören. Ein späterer Hash einer beliebigen Pfadangabe ist
   kein Beweis dafür. Mutationen zwischen Hash und Laden runnerseitig vermeiden.
3. Nach Prozessende Ergebnisse sammeln und `run_evidence.json` atomar schreiben.
   Der Beleg enthält Lauf-ID, Szenario, Hash der gestarteten ROM sowie SHA-256
   von Textlog, mGBA-Log, DONE, allen vorhandenen Root-PNG-Dateien (auch
   strukturell abgelehnten) und vorhandenen
   ABSTURZ.txt/FREEZE.txt. `_duplikate/` und andere Unterordner ignorieren.
4. Checker mit aktueller erwarteter Lauf-ID aufrufen und Exitcode prüfen.
   Keine Vermischung paralleler Szenarien. Runner-Exitcode und bestehende
   Text-/Rand-/Absturz-Gates bleiben zusätzlich maßgeblich.

## Vorgeschlagenes JSON-Schema 1

```json
{
  "schema": 1,
  "run_id": "synthetic-fresh-id",
  "scenario": "synthetic-menu",
  "launched_rom_sha256": "<64 Hexziffern>",
  "artifacts": {
    "druckerlog.txt": "<64 Hexziffern>",
    "mgba.log": "<64 Hexziffern>",
    "DONE": "<64 Hexziffern>",
    "0001.png": "<64 Hexziffern>"
  }
}
```

Diese Platzhalter sind Dokumentation, kein gültiger Testdatensatz.
`artifacts` muss exakt zu den tatsächlich verwendeten Laufbelegen passen.
JSON-Datei selbst, Manifest und ROM gehören nicht in diese Artefaktliste.
Echte Szenarionamen, Manifest-Adressen und Daten bleiben privat.

    python3 coverage_check.py --manifest /privat/manifest.json --rom /privat/build.gba --run-dir /privat/frischer-lauf --require-binding --run-id AKTUELLE_RUNNER_ID

Fehlender Beleg, falsche Lauf-ID/Szenario/ROM, fehlende oder zusätzliche
Artefakte und abweichende Hashes führen zu rot. Ungültiger JSON-Input führt
zu Exit 1. Ausgabe enthält nur Status/Grundcodes, keine Beleginhalte.

## Aussagegrenze

`binding: matched` bestätigt den Abgleich gegen den gelieferten Beleg und die
extern vorgegebene Lauf-ID. Es attestiert keinen ehrlichen Runner und beweist
nicht selbst die tatsächliche Emulator-Ausführung. Ein nachträglich aus alten
Dateien erzeugter Beleg ist kein Ersatz für die Start-/Abschluss-Integration.
Keine automatische Release-Freigabe, kein Live-Deployment. Erst enger privater
Testdatensatz oder Integration durch Runner-Owner, danach echte Gegenprobe.

## Zuständigkeit bestätigt

Nevio bestätigt im Kommentar 6474894058: I1 übernimmt den Runner-Adapter nach
seiner Rückkehr; der Vertrag passt konzeptionell. Feldnamen, Zeitpunkte,
frischer exklusiver Laufordner und Hash der tatsächlich gestarteten eigenen
ROM-Kopie sind von I1 abzugleichen. Keine direkten Änderungen an bot_run.py
oder der Live-Pipeline. Ein enger privater Datensatz genügt bei Bedarf.
Leeres mgba.log trat laut Nevio in 166 vorhandenen abgeschlossenen Läufen
keinmal auf; die konservative Prüfung bleibt für diesen Runner bestehen.

## Dateikonsistenz ist getrennt von PNG-Struktur

Eine beschädigte Bilddatei kann einen passenden SHA-256 im Beleg haben.
Darum umfasst das Artefakt-Set auch ungültige Root-PNG-Dateien; deren Bytes
werden unverändert gehasht. Die separate Struktur-/CRC-Prüfung kann gleichzeitig
`screenshots_invalid` melden. `binding: matched` macht diese Dateibefunde
nicht grün. Keine Aussage zu Bildinhalt, vollständiger Dekodierbarkeit oder
einer tatsächlichen Emulator-Ausführung daraus ableiten.
