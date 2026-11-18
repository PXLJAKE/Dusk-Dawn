# Hardware: Komponenten und Verdrahtung

Preise sind grobe Richtwerte (Stand 11/2026, Deutschland). Die Lautsprecher- und Passivmembran-Maße stecken als Parameter im Gehäuse ([`gehaeuse/soundlampe.scad`](../gehaeuse/soundlampe.scad)). Wer andere Chassis kauft, passt dort die Werte an.

## Warum Raspberry Pi statt ESP32?

Der ESP32 kann Sounds abspielen. Für die gewünschten Extras reicht er aber nicht:

| Wunsch | ESP32 | Raspberry Pi Zero 2 W |
|---|---|---|
| Mehrere Klang-Ebenen live mischen | knapp, viel Handarbeit | problemlos (ca. 10 % CPU für 10 Ebenen) |
| **Musikplayer in Home Assistant** (Music Assistant, Spotify, Radio) | nur einfache Stream-Wiedergabe | ja: squeezelite, Music Assistant erkennt die Lampe automatisch |
| Sounds und Musik gleichzeitig | nein | ja (ALSA dmix) |
| Guter Klang | MAX98357A 3 W, rauscht leise | DigiAMP+ mit 2 × 35 W, sauberer DAC, Lautstärke in Hardware |
| Lampe, Aufwachlicht, Home Assistant | ja | ja, alles in einem Programm |

Der Pi braucht etwas mehr Strom (ca. 1 W im Leerlauf). Dafür ist das Gerät ein vollwertiger Smart Speaker.

## Stückliste

### Elektronik

| Teil | Empfehlung | Preis ca. |
|---|---|---|
| Rechner | **Raspberry Pi 3 Model A+** (Standard im Gehäuse) oder **Raspberry Pi Zero 2 WH** (dann `pi_model = "zero2"` in `soundlampe.scad`). Kein Pi 4/5: zu groß, zu warm, zu viel Strom | 25–35 € |
| DAC + Verstärker | **Raspberry Pi DigiAMP+** (2 × 35 W, 12–24 V, versorgt auch den Pi) | 30 € |
| Netzteil | 19 V / 3,42 A (Laptop-Typ, Hohlstecker 5,5 × 2,5) oder 24 V / 2,5 A | 15 € |
| Einbaubuchse | DC-Einbaubuchse 5,5 × 2,1/2,5 mm, Loch 11 mm | 2 € |
| Step-down 5 V | **LM2596-Modul** (ca. 43 × 21 mm, Löcher 30 × 16 mm diagonal), vor dem Anschließen der LEDs auf 5,1 V einstellen | 3 € |
| Speicherkarte | microSD 32 GB, A1 | 7 € |
| LEDs | **SK6812 RGBW** Strip, 60 LED/m, **warmweiß (3000 K)**, 5 V, 0,5 m (30 LEDs) | 8 € |
| Pegelwandler | 74AHCT125 (DIP) + 330 Ω Widerstand + 1000 µF/10 V Elko | 2 € |
| Drehknopf | Drehgeber **EC11** mit Taster, 20 Rasten, 6-mm-D-Achse | 2 € |
| Kleinkram | Litzen, JST-Stecker, Schrumpfschlauch, Lochrasterstück | 6 € |

### Akustik

| Teil | Empfehlung | Preis ca. |
|---|---|---|
| Breitbänder | **Dayton Audio ND105-4** (4", 4 Ω), alternativ Visaton FRS 10 / Tang Band W4-1337 | 30 € |
| Passivmembran | **Dayton Audio ND105-PR** (oder ND90-PR, dann `pr_*`-Werte anpassen) | 15 € |
| Dämmung | Polyesterwatte (z. B. Sonofil), lose, ca. 20 g | 5 € |
| Entdröhnung | Alubutyl-Matte 2 mm, ca. 20 × 30 cm, innen an die Kammerwände | 6 € |
| Dichtung | Moosgummi-Dichtband 3 mm + etwas Silikon/Heißkleber | 4 € |

Warum so: Ein guter 4"-Breitbänder in einer geschlossenen Kammer von gut 2 l mit Passivmembran nach hinten liefert erstaunlich viel Bass. Das ist wichtig für Wellen, Gewitter und Brown Noise, und auch Musik klingt voll. Im Lampenfuß bringt Stereo keine echte Trennung, deshalb läuft das Gerät mono (beide Kanäle werden gemischt) und das Geld steckt in einem besseren Chassis.

### Mechanik

| Teil | Empfehlung | Preis ca. |
|---|---|---|
| Lampenstiel | **Messingrohr 20 mm**, 150 mm lang (oder gedruckt: `stem.stl`) | 6 € |
| Gewindeeinsätze | M3 Heat-Set-Inserts, ca. 30 Stück | 5 € |
| Schrauben | M3 × 8/10/12 (Linsenkopf), M2,5 × 6 für die Platinen, 4 × M2,5-Abstandsbolzen 11 mm (Pi Zero: 2 ×) | 5 € |
| Füße | 3 Gummifüße Ø 12 mm, selbstklebend | 2 € |
| Filament | ca. 600 g PETG (Fuß, dunkel) + ca. 150 g transluzentes PLA/PETG (Schirm, Elfenbein/Natur) | 25 € |

**Summe: ca. 195–225 €.** Zum Vergleich: Der Hatch Restore 3 kostet ca. 170 $ und kann weder mischen noch Musik aus Home Assistant spielen.

## Verdrahtung

```
 19 V Netzteil ──► DC-Buchse (hinten unten)
                     │
                     ├──► DigiAMP+ Eingang (12–24 V) ──► versorgt den Pi über die Stiftleiste
                     │         └─ Lautsprecher-Ausgang L ──► Breitbänder ND105-4  (R bleibt frei)
                     │
                     └──► Step-down auf 5,1 V ──┬─► LED-Strip +5V / GND
                                                ├─► 1000 µF Elko direkt am Strip-Anfang
                                                └─► 74AHCT125 VCC / GND

 Pi GPIO10 (SPI MOSI, Pin 19) ──► 74AHCT125 Eingang 1A   (1OE an GND)
 74AHCT125 Ausgang 1Y ──► 330 Ω ──► LED DIN

 Drehgeber EC11:  A ──► GPIO5  (Pin 29)
                  B ──► GPIO6  (Pin 31)
                  C ──► GND    (Pin 30)
                  Taster ──► GPIO13 (Pin 33), anderer Taster-Pin ──► GND (Pin 34)

 GND von Step-down, Pi und Pegelwandler gemeinsam verbinden.
```

Vom DigiAMP+ belegt (nicht anderweitig nutzen): GPIO2/3 (I²C), GPIO18–21 (I²S), GPIO22 (Stummschaltung).

| Funktion | GPIO (BCM) | Pin |
|---|---|---|
| LED-Daten (über 74AHCT125) | 10 | 19 |
| Drehgeber A | 5 | 29 |
| Drehgeber B | 6 | 31 |
| Drehgeber Taster | 13 | 33 |
| GND | – | 30, 34, 39 |

**Bedienung am Gerät:** Drehen ändert die Lautstärke (für Sounds und Musik). Ein Druck schaltet die Sounds an oder aus. Langes Drücken (1,2 s) schaltet die Lampe.

## Hinweise

- **LED-Strom:** 30 SK6812 RGBW ziehen bei voller Helligkeit bis zu 2 A. Die Software begrenzt auf 70 % (`led.max_brightness`). Der Step-down sollte 3 A können.
- **Wärme:** Der Lichtkern sitzt im offenen Schirm, trotzdem PETG für `led_core` nehmen und nicht über 70 % Dauerhelligkeit gehen.
- **Lautstärke nachts:** Der DigiAMP+ regelt die Lautstärke in Hardware. Deshalb bleibt auch bei sehr leise eingestellten Sounds kein Grundrauschen hörbar, anders als beim MAX98357A.
- **Gehäuse und Material:** Der Fuß wird mit 4 mm Wand (100 % Perimeter) und 8 Versteifungsrippen gedruckt, aus PETG statt PLA (wärmefester, kriecht nicht). Details und Begründung: [enclosure/README.md](../enclosure/README.md#akustik-und-material).
- **Dichtheit:** Die Lautsprecherkammer muss luftdicht sein, sonst arbeitet die Passivmembran nicht. Deckel und Zwischenboden mit Moosgummi abdichten, Kabeldurchführungen und das Gewinde des seitlichen Drehgebers mit Silikon schließen.
