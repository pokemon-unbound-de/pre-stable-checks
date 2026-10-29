# CX-038 – beschädigte Screenshot-Dateien im isolierten Bot-Pilot erkennen

## Problem und beobachtete Änderung

Am Stand6e90451 zählte eine Datei bereits mit acht PNG-Signaturbytes als
Screenshot. Synthetischer Gegenbeleg:17 Dateien nur mit Dateikopf, dazu passende
Lauf-ID und neu berechnete Artefakt-Hashes. Der alte Checker meldete17 Bilder,
`binding: matched`, Coveragegrün und Exit0. Das entsprach der bisherigen
Signaturzählung, belegte aber keine intakten Bilddateien.

Jetzt zählt der Checker nur Dateien, deren PNG-Kernstruktur und Chunk-CRCs
bestehen. Derselbe Fall liefert0 gezählte Bilder,17 ungültige Dateien,
`binding: matched`, Coverage rot und Exit2. Grundcodes:
`screenshots_insufficient` und `screenshots_invalid`. Auch eine zusätzliche
beschädigte Root-PNG macht einen sonst ausreichend bebilderten Lauf rot.
Diese stärkere lokale Pilotregel benötigt weiterhin die Projektabnahme.

Die Aggregate samt Codehashes stehen in `png_evidence_repro.json`. Alle
Eingaben sind vollständig synthetisch; keine Spiel-ROM, echten Logs oder
Screenshots werden mitgeliefert. Es wurde kein Emulator ausgeführt.

## Was geprüft wird

`png_evidence.py` verwendet nur die Standardbibliothek und liest Chunkdaten
in Blöcken bis64KiB, ohne Bildpixel zu dekomprimieren. Geprüft werden:

- PNG-Signatur, vollständige Chunkrahmen/-längen und CRCs;
- ein erstes IHDR mit zulässigen Grundfeldern und positiven Bildmaßen;
- erforderliche Palette bei indizierten Bildern, grundlegende Palettenposition;
- zusammenhängende IDAT-Chunks mit insgesamt nichtleerer Nutzlast;
- abschließendes IEND ohne nachfolgende Bytes; unbekannte kritische Chunks
  werden konservativ abgelehnt.

Grundlage: [W3C PNG-Spezifikation](https://www.w3.org/TR/png/), insbesondere
Dateistruktur, kritische Chunks, IHDR-Felder und CRC. Das ist keine vollständige
Implementierung eines PNG-Decoders. IDAT-Dekompression, Scanline-/Filterdaten,
Bildinhalt, Spielzustand und die Semantik aller Zusatzchunks bleiben ungeprüft.
Eine Datei mit korrekter Rahmung/CRC und ungeeignetem komprimiertem Raster kann
hier weiterhin bestehen; diese Grenze hat einen ausdrücklichen Regressionstest.

Die bestehenden Root-/Unterordner-Regeln bleiben gleich. Binding hasht auch
strukturell abgelehnte Dateien, damit ein identischer Hash nicht mit intakten
Bilddaten verwechselt wird. Reale Dateilesefehler bleiben Eingabefehler/Exit1;
strukturell beschädigte Bilder sind ein Laufbefund/Exit2.

## Prüfungen und Integration

Ab `bot_coverage/`:

```sh
python3 -m unittest discover -s tests -v
python3 replay_checks.py
```

39/39 Tests bestanden, darunter11 neue PNG-/Datei-Gegenproben. Replay14/14
entspricht den Erwartungen (1 gültig,13 negativ,0 falsch grün); der neue Fall
`truncated_png_bound` weist trotz matched-Binding17 ungültige Dateien aus.
Positive Tests benutzen jetzt vollständige generierte1×1-PNGs.

Nur `bot_coverage/` im bestehenden Draft-PR wird geändert. Keine Änderung an
`tools/bot_run.py`, ROM/Builder, Live-Pipeline oder Pflichtgates. I1 bleibt Owner
der tatsächlichen Runner-Anbindung. Reale Runner-Gegenprobe und Abnahme fehlen;
die synthetischen Tests sind keine Freigabe für einen Release.
