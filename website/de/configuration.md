# Konfiguration

Dusk & Dawn wird komplett über die Oberfläche eingerichtet. YAML ist nicht nötig.

## Schlafplatz anlegen

Ein **Schlafplatz** verbindet Lautsprecher, Lampen und optional einen Präsenzmelder. Angelegt wird er unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → Dusk & Dawn**.

| Feld | Bedeutung |
| --- | --- |
| **Name** | Name des Schlafplatzes, zum Beispiel „Schlafzimmer“. Pflichtfeld, muss eindeutig sein. |
| **Lautsprecher** | Media Player, die die Einschlafklänge abspielen (als Stream). |
| **Lampen** | Lampen für Nachtlicht, Einschlaf-Dimmen und Sonnenaufgang. |
| **Präsenzmelder** | Optionaler Präsenz- oder Bewegungsmelder für automatischen Start und Stopp. |
| **DIY-Soundlampe (MQTT-Geräte-ID)** | Nur für eine selbst gebaute [Soundlampe](sound-lamp.md), zum Beispiel `sleepgen`. Sie spielt Klänge und Lichteffekte dann selbst, statt zu streamen. |

## Mehrere Zimmer

Für jedes weitere Zimmer die Integration einfach noch einmal hinzufügen. Jeder Schlafplatz hat eigene Lautsprecher, Lampen, Szenen-Auswahl, Wecker und Automatik.

## Einstellungen später ändern

Lautsprecher, Lampen und Melder lassen sich jederzeit ändern:

- in der Seitenleiste über das **Zahnrad**, oder
- unter **Einstellungen → Geräte & Dienste → Dusk & Dawn → Konfigurieren**. Dort lässt sich auch der Name ändern.

## Design der Seitenleiste

Über **Sonne/Mond** oben rechts in der Seitenleiste wechselst du das Design: wie Home Assistant (automatisch), hell oder dunkel. Die Wahl merkt sich jeder Browser selbst.

## Sprache

Seitenleiste und Einstellungsdialoge gibt es auf Deutsch und Englisch. Die Seitenleiste folgt der Sprache deines Home-Assistant-Profils: Deutsch, wenn sie mit „de“ beginnt, sonst Englisch.
