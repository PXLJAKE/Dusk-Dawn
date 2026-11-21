# Eigene Aufnahmen statt Synthese

Für **Regen, Meereswellen, Wind, Vögel, Blätterrauschen und Kaminfeuer** kannst du eigene Aufnahmen hochladen (Handy, Diktiergerät, freie Sound-Archive). Je länger, desto besser: ab 5 Minuten klingt es nicht mehr nach Schleife.

## So geht es

1. Seitenleiste **Dusk & Dawn → Klänge**, ganz unten die Karte **Eigene Aufnahmen**.
2. Beim gewünschten Klang **Aufnahme hochladen** (nur Administratoren). Jedes Format, das ffmpeg liest: WAV, MP3, FLAC, OGG, M4A, AAC, auch Video (nur der Ton wird genommen). Bis 400 MB pro Datei, mindestens 3 Sekunden.
3. **Eigene Datei** antippen. Ab jetzt ersetzt die Aufnahme die Synthese; Regler, Presets, Timer und Lautstärke funktionieren wie bisher. „Synthetisch“ schaltet zurück.

Pro Klang sind bis zu 12 Dateien möglich, sie wechseln sich ab. Die Aufnahmen liegen im HA-Ordner `dusk_dawn_sounds/` (nicht im Backup der Integration, bitte mitsichern) und gelten für alle Schlafplätze.

## Wie die Wiederholung versteckt wird

- Beim Hochladen wird jede Datei einmal zu Mono dekodiert und auf eine einheitliche Lautstärke gebracht, damit sie neben den synthetischen Klängen nicht lauter oder leiser ist.
- Abgespielt wird eine Kette aus zufälligen Ausschnitten (45 bis 150 Sekunden) mit 6 Sekunden langen Überblendungen (gleiche Leistung, kein Pegeleinbruch). Start und Länge sind jedes Mal anders, bei mehreren Dateien wechseln sie sich ab.
- Ein langsames Lautstärkeschwanken von ±1,2 dB über knapp eine Minute verhindert, dass das Bett statisch wirkt.

**Aufnahme-Tipps:** Mikrofon nicht in die Windrichtung, kein Handgeräusch, kein Sprechen oder Auto im Hintergrund; bei Regen und Meer lieber Mono-Abstand als Stereo-Nähe. Vögel brauchen eine ruhige Stelle ohne Verkehr, sonst hört man das Brummen in jeder Schleife.

## Pi-Soundlampe

Auf der Lampe (ohne HA-Stream) ersetzt in `config.yaml` ein Eintrag wie `rain=file:/home/admin/sounds/regen` die Synthese durch eine Datei **oder einen Ordner** mit mehreren Dateien (gleiche Technik, `ffmpeg` wird vom Installer mitinstalliert). Mit `file:/pfad/zur/datei.mp3` entsteht eine zusätzliche Ebene. Ein Upload aus dem Seitenpanel zur Lampe gibt es noch nicht.
