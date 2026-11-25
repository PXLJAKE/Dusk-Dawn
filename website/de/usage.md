# Seitenleiste

Nach der Einrichtung erscheint links in Home Assistant der Eintrag **Dusk & Dawn**. Die Seitenleiste hat mehrere Bereiche.

![Klänge in der Seitenleiste](assets/img/desktop-sounds.png)

## Jetzt

Start und Stopp, Lautstärke, Sleep-Timer, Licht und deine Szenen zum Antippen.

![Jetzt-Ansicht auf dem Handy](assets/img/mobile-now.png){ width="320" }

## Szenen

Eine Szene startet Klänge (auch eigene) und kann zusätzlich **Lautstärke**, **Sleep-Timer** und **Licht** setzen. Für das Licht gibt es:

- Aus
- Weiß
- Farbe
- Farbverlauf, zum Beispiel von Orange zu Dunkelviolett über 30 Minuten. Helligkeit 0 am Ende schaltet das Licht aus.
- Kerze
- Einschlaflicht: warmes, gedimmtes Licht, das mit dem Sleep-Timer ausgeht

Eigene Szenen stehen immer oben und lassen sich per Drag and Drop am Griff (oder mit den Pfeiltasten) sortieren. Die mitgelieferten Szenen wie **Gute Nacht** sind Vorschläge: Du kannst sie bearbeiten, entfernen und wiederherstellen.

## Klänge

Szenen antippen oder im **Mischpult** jeden Klang einzeln einstellen und als eigene Szene speichern. Eingebaut sind acht Klänge:

Regen, Meer, Wind, Gewitter, Ventilator, White Noise, Pink Noise und Brown Noise.

Die Gruppe **Eigene** zeigt deine eigenen Klänge, siehe [Eigene Klänge](own-sounds.md).

## Sleep-Timer

Der Sleep-Timer blendet die Klänge zum Schluss sanft aus, höchstens über die letzten 10 Minuten. In der Entität **Sleep-Timer** stehen Aus, 15, 30, 45, 60 und 90 Minuten zur Wahl. Ein ausgeschalteter Sleep-Timer bleibt aus, auch wenn die Automatik startet.

## Wecker

Beliebig viele Weckzeiten mit:

- Wochentagen
- Weckton **Glocken** oder **Klassisch**, mit Vorhören
- Dauer und Lautstärke
- Sonnenaufgang auf den Lampen davor

## Automatik

Die Automatik startet die gewählte Abendszene (Standard „Gute Nacht“) in einem Zeitfenster. Zwei Arten:

- **Mit Präsenzmelder:** Start erst, wenn jemand mindestens 10 Minuten (einstellbar) im Raum ist. Aus, wenn niemand mehr da ist.
- **Nur nach Zeitraum:** ohne Sensor, Start zu Beginn und Stopp am Ende des Zeitfensters.

Läuft auf dem Lautsprecher Musik, pausiert die Automatik.

## Lautstärke

Die Klänge sind absichtlich leiser als Musik über AirPlay oder Music Assistant:

- Regler ganz oben entspricht −18 dB.
- Bei 50 % sind es etwa −38 dB.
- Der Wecker ist zusätzlich um 12 dB gedämpft.

Mit der DIY-Soundlampe rechnet die Lampe diese Kurve selbst. Sie braucht dafür das aktuelle Update der Lampen-Software.

## Zahnrad und Design

- **Zahnrad:** Lautsprecher, Lampen und Melder ändern, siehe [Konfiguration](configuration.md).
- **Sonne/Mond oben rechts:** Design wechseln.
