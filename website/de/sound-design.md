# Wie die Klänge entstehen

Die eingebauten Klänge sind keine Aufnahmen. Jeder wird live berechnet: in Home Assistant vom Klangkern in Rust und, bei der optionalen Soundlampe, direkt auf dem Raspberry Pi. Beide rechnen dieselben Klänge.

Das hat drei Vorteile:

- **Keine Schleife.** Eine Aufnahme wiederholt sich irgendwann, und das Ohr findet die Stelle. Ein berechneter Klang wiederholt sich nie.
- **Alles ist einstellbar.** Jede Ebene hat ihren eigenen Regler und lässt sich mit allen anderen mischen.
- **Keine Lizenzfragen**, kein Speicherplatz. Eigene Aufnahmen gehen trotzdem, siehe [Eigene Klänge](own-sounds.md).

## Wo gerechnet wird

**Als reine Integration** (normaler Lautsprecher): Home Assistant berechnet die Geräusche selbst und stellt sie als MP3-Stream bereit, den der Lautsprecher wie ein Internetradio abspielt. Dadurch reagieren Sonos- und Google-Lautsprecher auf Regler mit 2 bis 10 Sekunden Verzögerung. Der Klangkern liegt für x86_64 und aarch64 fertig gebaut bei und braucht für vier Klänge etwa 0,5 % eines CPU-Kerns. Auf anderen Systemen nutzt die Integration automatisch eine langsamere Python-Version mit gleichem Klang. Eigene Klänge werden von Home Assistant abgespielt und gemischt.

**Mit der Soundlampe:** Die Lampe bekommt nur Befehle über MQTT und berechnet die Klänge selbst auf dem Raspberry Pi, ohne Verzögerung. Auch die Weckzeiten speichert die Lampe selbst, der Wecker klingelt also auch, wenn Home Assistant oder das WLAN ausfällt.

## Bausteine

Die Klänge bestehen aus zwei Teilen:

1. **Ein Teppich aus Rauschen**, der den Raum füllt. Filter formen das Rauschen, langsame Zufallskurven bewegen Lautstärke und Filter, damit nichts statisch klingt.
2. **Viele kurze Ereignisse**, an denen das Ohr den Klang erkennt, zum Beispiel ein einzelner Tropfen oder eine Luftblase. Sie werden zufällig über Zeit, Lautstärke und Stereobild verstreut. Ein Teil davon ist deutlich lauter als der Rest, das klingt nach Nähe.

Die ausführliche Beschreibung jedes Klangs mit Spektren und Kurven steht in [SOUND_DESIGN.md auf GitHub](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/docs/SOUND_DESIGN.md). Der Code liegt in [`core/`](https://github.com/PXLJAKE/Dusk-Dawn/tree/main/core) (Rust) und [`custom_components/dusk_dawn/engine/`](https://github.com/PXLJAKE/Dusk-Dawn/tree/main/custom_components/dusk_dawn/engine) (Python-Ersatz).
