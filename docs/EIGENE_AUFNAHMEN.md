# Eigene Klänge und Aufnahmen

Zusätzlich zu den acht eingebauten, berechneten Klängen kannst du **beliebig viele eigene Klänge** anlegen, benennen und mit eigenen Aufnahmen füllen (Handy, Diktiergerät, freie Sound-Archive). Ein eigener Klang erscheint im Mischpult wie jeder andere, lässt sich in Klangwelten mischen und wird endlos ohne hörbare Schleife abgespielt. Je länger die Aufnahme, desto besser: ab 5 Minuten klingt es nicht mehr nach Schleife.

## So geht es

1. Seitenleiste **Dusk & Dawn → Klänge**, Karte **Eigene Klänge**.
2. Name eingeben (z. B. „Regen am Zeltdach“, „Waldbach“) und **Anlegen**. Umbenennen geht jederzeit.
3. Beim Klang **Aufnahme hochladen** (nur Administratoren). Jedes Format, das ffmpeg liest: WAV, MP3, FLAC, OGG, M4A, AAC, auch Video (nur der Ton wird genommen). Bis 400 MB pro Datei, mindestens 3 Sekunden.
4. Der Klang taucht in der Gruppe **Eigene** im Mischpult auf. Regler, Klangwelten, Timer und Lautstärke funktionieren wie bei den eingebauten Klängen.

Pro eigenem Klang sind bis zu 12 Dateien möglich, sie wechseln sich ab. Löschen eines Klangs entfernt auch seine Dateien und nimmt ihn aus allen Klangwelten. Die Aufnahmen liegen im HA-Ordner `dusk_dawn_sounds/` (nicht im Backup der Integration, bitte mitsichern) und gelten für alle Schlafplätze.

*Hinweis zu Version 0.3.0:* Wer dort Aufnahmen für Regen, Meer & Co. hochgeladen hatte, findet sie beim Update als eigene Klänge „… (eigene Aufnahme)“ wieder. Die Klänge Bach, Vögel, Blätter und Feuer gibt es nicht mehr als eingebaute Klänge, nur noch als eigene Aufnahme.

## Wie die Wiederholung versteckt wird

- Beim Hochladen wird jede Datei einmal zu Mono dekodiert und auf eine einheitliche Lautstärke gebracht, damit sie neben den berechneten Klängen nicht lauter oder leiser ist.
- Abgespielt wird eine Kette aus zufälligen Ausschnitten (45 bis 150 Sekunden) mit 6 Sekunden langen Überblendungen (gleiche Leistung, kein Pegeleinbruch). Start und Länge sind jedes Mal anders, bei mehreren Dateien wechseln sie sich ab.
- Ein langsames Lautstärkeschwanken von ±1,2 dB über knapp eine Minute verhindert, dass das Bett statisch wirkt.

**Aufnahme-Tipps:** Mikrofon nicht in die Windrichtung, kein Handgeräusch, kein Sprechen oder Auto im Hintergrund; bei Regen und Meer lieber Mono-Abstand als Stereo-Nähe. Vögel brauchen eine ruhige Stelle ohne Verkehr, sonst hört man das Brummen in jeder Schleife.

## Mit der DIY-Soundlampe

Eigene Klänge aus der Seitenleiste werden von Home Assistant abgespielt, laufen also nicht auf der Soundlampe. Auf der Lampe selbst ersetzt in `config.yaml` ein Eintrag wie `rain=file:/home/admin/sounds/regen` die Berechnung durch eine Datei **oder einen Ordner** mit mehreren Dateien (gleiche Technik, `ffmpeg` wird vom Installer mitinstalliert). Mit `file:/pfad/zur/datei.mp3` entsteht eine zusätzliche Ebene. Ein Upload aus der Seitenleiste zur Lampe gibt es nicht.
