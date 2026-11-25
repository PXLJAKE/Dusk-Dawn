# Installation

## Voraussetzungen

- Home Assistant **2025.1** oder neuer.
- Ein Lautsprecher, der in Home Assistant als **Media Player** erscheint, zum Beispiel Sonos, Google/Nest, Music Assistant, Squeezebox oder AirPlay.
- Optional: Lampen (`light`-Entitäten) und ein Präsenz- oder Bewegungsmelder.

!!! warning "Echo/Alexa geht nicht"
    Echo- und Alexa-Lautsprecher spielen keine eigenen Streams ab und lassen sich deshalb nicht verwenden.

Eigene Hardware ist nicht nötig. Die [Soundlampe](sound-lamp.md) ist nur ein optionales Gerät.

## Über HACS installieren

[![Repository in HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PXLJAKE&repository=Dusk-Dawn&category=integration)

1. In HACS **Dusk & Dawn** suchen und **Herunterladen**. Ist die Integration noch nicht im Standard-Katalog: ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/PXLJAKE/Dusk-Dawn`, Typ **Integration**, hinzufügen.
2. Home Assistant **neu starten**.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Dusk & Dawn** und den ersten Schlafplatz anlegen, siehe [Konfiguration](configuration.md).

Danach erscheint links in der Seitenleiste **Dusk & Dawn**.

## Updates

Jede neue Version wird als GitHub-Release veröffentlicht. HACS bietet sie danach automatisch als Update an. Was sich geändert hat, steht unter [Änderungen](changelog.md).

## Manuelle Installation ohne HACS

!!! warning "Offen"
    Eine Anleitung für die Installation ohne HACS gibt es im Projekt bisher nicht.

## Deinstallieren

!!! warning "Offen"
    Ein beschriebener Weg zum Entfernen (inklusive der eigenen Aufnahmen im Ordner `dusk_dawn_sounds/`) ist im Projekt bisher nicht dokumentiert.
