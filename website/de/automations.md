# Automationen

Für eigene Automationen, Skripte und Dashboards legt Dusk & Dawn **pro Schlafplatz** Entitäten und Aktionen an. Für die normale Bedienung brauchst du sie nicht, dafür gibt es die [Seitenleiste](usage.md).

## Entitäten

| Entität | Typ | Bedeutung |
| --- | --- | --- |
| Klänge | Schalter | Klänge an/aus |
| Wecker | Schalter | alle Wecker des Schlafplatzes an/aus |
| Klang | Auswahl | aktive Szene; die Optionen sind die Namen deiner Szenen |
| Sleep-Timer | Auswahl | Aus, 15, 30, 45, 60 oder 90 Minuten |
| Lautstärke | Zahl | 0 bis 100 % |
| Regen, Meereswellen, Wind, Gewitter, Ventilator, White/Pink/Brown Noise | Zahl | Pegel jedes eingebauten Klangs, 0 bis 100 %. Standardmäßig sind nur Regen, Meereswellen und Brown Noise aktiviert, die anderen lassen sich in den Entitäts-Einstellungen einschalten. |
| Nächster Wecker | Sensor | Zeitpunkt des nächsten Weckers |
| Weckzeit | Zeit | Uhrzeit des ersten Weckers; setzen legt einen Wecker an, falls noch keiner existiert |
| Wecker klingelt | Binärsensor | an, solange ein Wecker klingelt |
| Gute Nacht | Taste | startet „Gute Nacht“ |
| Wecker stoppen | Taste | stoppt einen klingelnden Wecker |

## Aktionen

Alle Aktionen gehören zur Domain `dusk_dawn`. Als Ziel wählst du eine Entität oder ein Gerät des Schlafplatzes. **Ohne Ziel wirkt die Aktion auf alle Schlafplätze.**

| Aktion | Felder | Wirkung |
| --- | --- | --- |
| `dusk_dawn.play` | `preset` (Name oder ID der Szene, optional), `volume` (0 bis 1), `timer` (Minuten, 0 bis 240; 0 schaltet den Timer aus) | startet die Einschlafklänge |
| `dusk_dawn.stop` | | stoppt die Einschlafklänge |
| `dusk_dawn.good_night` | | startet den Gute-Nacht-Klang mit Sleep-Timer und dimmt das Licht |
| `dusk_dawn.ring` | `tone` (`bells` oder `classic`), `duration` (1 bis 60 Minuten) | lässt den Wecker jetzt klingeln |
| `dusk_dawn.stop_alarm` | | stoppt einen klingelnden Wecker |

## Beispiel

Regen mit 30 Minuten Sleep-Timer starten, wenn eine bestimmte Taste gedrückt wird (Taste und Szenenname anpassen):

```yaml
automation:
  - alias: "Einschlafen mit Regen"
    triggers:
      - trigger: state
        entity_id: input_button.bett   # deine Taste
    actions:
      - action: dusk_dawn.play
        data:
          preset: Regen                # Name deiner Szene
          volume: 0.4
          timer: 30
```

Ohne `target` startet das auf allen Schlafplätzen. Für ein Zimmer ergänzt du ein `target` mit einer Entität oder dem Gerät dieses Schlafplatzes.
