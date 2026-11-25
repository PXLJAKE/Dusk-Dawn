# Fehlersuche

Die meisten Hinweise stehen im Log von Home Assistant: **Einstellungen → System → Protokolle**, nach „dusk_dawn“ filtern.

## Mehr Details im Log

Für ausführlichere Meldungen kannst du das Debug-Log der Integration einschalten: **Einstellungen → Geräte & Dienste → Dusk & Dawn → Debug-Protokollierung aktivieren**. Alternativ in `configuration.yaml` über die [Logger-Integration](https://www.home-assistant.io/integrations/logger/):

```yaml
logger:
  logs:
    custom_components.dusk_dawn: debug
```

## Der Lautsprecher spielt nichts

**Im Log steht „No internal URL available; set one under Settings > System > Network“.**
Der Lautsprecher holt den Stream über die interne Adresse von Home Assistant. Trag sie unter **Einstellungen → System → Netzwerk** ein.

**Im Log steht „Cannot start ffmpeg“.**
Die Klänge werden mit ffmpeg zu MP3 kodiert. Dusk & Dawn nutzt das ffmpeg, das in Home Assistant eingerichtet ist (Integration *FFmpeg*), sonst den Befehl `ffmpeg`. Prüfe, ob ffmpeg auf deinem System vorhanden ist.

**Im Log steht „Encoder for … ended unexpectedly“.**
Der Encoder ist während der Wiedergabe beendet worden.

!!! warning "Offen"
    Ursachen und Abhilfe für „Encoder … ended unexpectedly“ sind im Projekt bisher nicht dokumentiert.

**Der Lautsprecher ist ein Echo/Alexa.**
Diese Geräte spielen keine eigenen Streams ab, siehe [FAQ](faq.md#welche-lautsprecher-funktionieren).

## Die Lampen reagieren nicht

Im Log steht dann eine Meldung wie „light.turn_on failed for …“ mit dem Fehler der Lampe. Prüfe, ob sich die Lampe in Home Assistant direkt schalten lässt und ob sie im Schlafplatz ausgewählt ist ([Konfiguration](configuration.md)).

## Die Soundlampe reagiert nicht

**Im Log steht „MQTT is not set up; the DIY lamp … cannot be controlled“.**
Die Soundlampe wird über MQTT gesteuert. Richte die MQTT-Integration und einen Broker ein, wie in [SETUP.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/SETUP.md) beschrieben, und prüfe die MQTT-Geräte-ID im Schlafplatz.

## Hochladen eigener Aufnahmen klappt nicht

| Meldung | Ursache |
| --- | --- |
| admin required | Nur Administratoren dürfen Aufnahmen hochladen. |
| file too large (max 400 MB) | Die Datei ist größer als 400 MB. |
| too short (… s, at least 3 s) | Die Aufnahme ist kürzer als 3 Sekunden. |

Andere Meldungen kommen meist von ffmpeg, wenn es die Datei nicht lesen kann.

## Welcher Klangkern läuft?

Beim Start schreibt Dusk & Dawn ins Log, ob der Rust-Klangkern („uses the Rust sound engine“) oder die langsamere Python-Version („uses the Python sound engine“) läuft. Die Python-Version klingt gleich, braucht aber mehr Rechenleistung.

## Die Seitenleiste zeigt nach einem Update die alte Version

Die Adresse der Seitenleiste enthält Version und Änderungszeit, damit der Browser nach einem Update die neue Datei lädt. Lade die Seite einmal neu. In der Browser-Konsole meldet die Seitenleiste ihre Version.

!!! warning "Offen"
    Hinweise für Installationen hinter einem Proxy oder CDN, das statische Dateien zwischenspeichert, sind im Projekt bisher nicht dokumentiert.

## Fehler melden

Hilft nichts davon, melde den Fehler bitte als [Issue auf GitHub](https://github.com/PXLJAKE/Dusk-Dawn/issues) mit Home-Assistant-Version, Lautsprecher-Typ und den passenden Zeilen aus dem Log.
