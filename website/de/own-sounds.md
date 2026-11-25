# Eigene Klänge

Zusätzlich zu den acht eingebauten, berechneten Klängen kannst du **beliebig viele eigene Klänge** anlegen, benennen und mit eigenen Aufnahmen füllen (Handy, Diktiergerät, freie Sound-Archive). Ein eigener Klang erscheint im Mischpult wie jeder andere, lässt sich in Szenen mischen und wird endlos ohne hörbare Schleife abgespielt. Je länger die Aufnahme, desto besser: ab 5 Minuten klingt es nicht mehr nach Schleife.

## So geht es

1. Seitenleiste **Dusk & Dawn → Klänge**, Karte **Eigene Klänge**.
2. Name eingeben (zum Beispiel „Regen am Zeltdach“ oder „Waldbach“) und **Anlegen**. Umbenennen geht jederzeit.
3. Beim Klang **Aufnahme hochladen**. Das dürfen nur Administratoren.
4. Der Klang taucht in der Gruppe **Eigene** im Mischpult auf. Regler, Szenen, Timer und Lautstärke funktionieren wie bei den eingebauten Klängen.

## Dateien

| Was | Vorgabe |
| --- | --- |
| Formate | alles, was ffmpeg lesen kann: WAV, MP3, FLAC, OGG, M4A, AAC, auch Video (nur der Ton wird genommen) |
| Größe | bis 400 MB pro Datei |
| Länge | mindestens 3 Sekunden, empfohlen 5 Minuten oder mehr |
| Anzahl | bis zu 12 Dateien pro Klang, sie wechseln sich ab |
| Speicherort | Home-Assistant-Ordner `dusk_dawn_sounds/`, gilt für alle Schlafplätze |

!!! note "Sichern"
    Die Aufnahmen liegen nicht im Backup der Integration. Bitte den Ordner `dusk_dawn_sounds/` selbst mitsichern.

Löschen eines Klangs entfernt auch seine Dateien und nimmt ihn aus allen Szenen.

## Wie die Wiederholung versteckt wird

- Beim Hochladen wird jede Datei einmal zu Mono dekodiert und auf eine einheitliche Lautstärke gebracht, damit sie neben den berechneten Klängen nicht lauter oder leiser ist.
- Abgespielt wird eine Kette aus zufälligen Ausschnitten (45 bis 150 Sekunden) mit 6 Sekunden langen Überblendungen ohne Pegeleinbruch. Start und Länge sind jedes Mal anders, mehrere Dateien wechseln sich ab.
- Ein langsames Lautstärkeschwanken von ±1,2 dB über knapp eine Minute verhindert, dass der Klang statisch wirkt.

## Aufnahme-Tipps

- Mikrofon nicht in die Windrichtung halten, keine Handgeräusche, kein Sprechen oder Auto im Hintergrund.
- Bei Regen und Meer lieber Abstand in Mono als Nähe in Stereo.
- Vögel brauchen eine ruhige Stelle ohne Verkehr, sonst hört man das Brummen in jeder Schleife.

## Mit der DIY-Soundlampe

Eigene Klänge aus der Seitenleiste werden von Home Assistant abgespielt, laufen also nicht auf der Soundlampe. Auf der Lampe selbst ersetzt in `config.yaml` ein Eintrag wie `rain=file:/home/admin/sounds/regen` die Berechnung durch eine Datei oder einen Ordner mit mehreren Dateien. Mit `file:/pfad/zur/datei.mp3` entsteht eine zusätzliche Ebene. Einen Upload aus der Seitenleiste zur Lampe gibt es nicht.

## Hinweis zu Version 0.3.0

Wer in Version 0.3.0 Aufnahmen für Regen, Meer und Co. hochgeladen hatte, findet sie nach dem Update als eigene Klänge „… (eigene Aufnahme)“ wieder. Bach, Vögel, Blätter und Feuer gibt es nicht mehr als eingebaute Klänge, nur noch als eigene Aufnahme.
