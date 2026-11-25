# Dusk & Dawn

**Dusk & Dawn** macht aus jedem Lautsprecher und jeder Lampe in Home Assistant eine Einschlafhilfe mit Wecker. Regen, Meer, Wind, Gewitter, Ventilator und White/Pink/Brown Noise lassen sich frei mischen, dazu kommen eigene Aufnahmen, eigene Szenen, Sleep-Timer, Lichtwecker mit Sonnenaufgang und eine Automatik per Präsenzmelder. Bedient wird alles in einer eigenen Seitenleiste. Helfer, Skripte oder YAML braucht es nicht.

![Seitenleiste von Dusk & Dawn](assets/img/desktop-alarms.png)

## Was die Integration kann

- **Klänge mischen:** acht eingebaute Klänge, einzeln regelbar und als Szene speicherbar. Die Klänge werden in Home Assistant berechnet (Klangkern in Rust, für x86_64 und aarch64 fertig dabei) und als Stream an den Lautsprecher geschickt. Es werden keine Audiodateien mitgeliefert, nichts wiederholt sich hörbar.
- **Eigene Klänge:** beliebig viele eigene Aufnahmen hochladen und benennen, siehe [Eigene Klänge](own-sounds.md).
- **Sleep-Timer** mit sanftem Ausblenden und **Wecker** mit mehreren Weckzeiten, Wochentagen, Weckton und Sonnenaufgang davor.
- **Licht:** Sonnenaufgang, Einschlaflicht, Farbe, Farbverlauf und Kerzenflackern auf jeder Lampe.
- **Automatik:** Start, wenn jemand mindestens 10 Minuten im Raum ist, oder nach Zeitfenster; Stopp, wenn niemand mehr da ist; Pause bei Musik.
- **Mehrere Zimmer:** jeder Schlafplatz hat eigenen Lautsprecher, eigene Lampen und eigene Einstellungen.

## Los geht's

1. [Voraussetzungen prüfen und installieren](installation.md)
2. [Schlafplatz einrichten](configuration.md)
3. [Seitenleiste kennenlernen](usage.md)

Fragen und Probleme: [FAQ](faq.md) und [Fehlersuche](troubleshooting.md).

## Optional: die Soundlampe

Die Integration funktioniert komplett ohne eigene Hardware. Wer will, baut sich zusätzlich die [Soundlampe](sound-lamp.md), eine Nachttischlampe mit Raspberry Pi, eingebautem Lautsprecher und LED-Lichtkern.

## Lizenz und Quellcode

Dusk & Dawn steht unter der [MIT-Lizenz](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/LICENSE). Quellcode, Issues und Releases: [github.com/PXLJAKE/Dusk-Dawn](https://github.com/PXLJAKE/Dusk-Dawn).
