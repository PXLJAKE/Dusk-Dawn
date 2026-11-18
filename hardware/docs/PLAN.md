# SleepGenerator – Soundlampe

Eine Retro-Tischlampe fürs Bett mit eingebautem Lautsprecher: Regen, Meer, Gewitter, Wind, Kaminfeuer, Vögel, Ventilator und White/Pink/Brown Noise, **frei mischbar**, mit Sleep-Timer, Aufwachlicht und **Musikplayer in Home Assistant**. Bedient wird sie per Drehknopf am Gerät und per Handy über Home Assistant.

- **Online-Demo:** [Soundlampe Demo](https://claude.ai/artifact/DLmL7VoFJZXLVwC1FM6WSx). Dieselben Klänge, Timer, Lampe und Sonnenaufgang laufen im Browser. Quellcode: [`docs/demo/index.html`](../../docs/demo/index.html)
- **Komponenten und Verdrahtung:** [HARDWARE.md](HARDWARE.md)
- **Gehäuse (3D-Druck):** [gehaeuse/](../gehaeuse/README.md)
- **Software auf dem Gerät:** [device/](../device)
- **Einrichtung inkl. Home Assistant und Musik:** [SETUP.md](SETUP.md)

![Soundlampe](../gehaeuse/renders/asm_kugel.png)

---

## 1. Was gibt es schon zu kaufen?

| Gerät | Preis (ca.) | Sounds | Mischen? | Bemerkung |
|---|---|---|---|---|
| **Hatch Restore 3** | 169,99 $ (+ optional Hatch+ 4,99 $/Monat) | 60+ | nicht dokumentiert | Kommt der Idee am nächsten: Wecker, Licht, Sounds, App. Teuer, Teile hinter Abo, kein Home Assistant |
| **Snooz / LectroFan** | 40–90 € | Lüfter, Rauschen | nein | Gutes Rauschen, keine Naturklänge |
| **Yogasleep Dohm / Whish** | 40–50 € | Lüfter bzw. wenige Klänge | nein | einfach |
| **Hammacher „120 Sound Machine“** | eingestellt | 18 + Zusätze | **ja** | das einzige Gerät mit echtem Mischen, nicht mehr erhältlich |

Echtes Mischen mehrerer Ebenen, Musik und Home Assistant bietet kein fertiges Gerät. Darum der Selbstbau.

Quellen: [Tom's Guide – Hatch Restore 3](https://www.tomsguide.com/wellness/sleep/hatch-launches-new-phone-free-sunrise-alarm-clock-with-more-sleep-sounds-and-no-extra-cost), [Hammacher](https://www.hammacher.com/product/customizable-120-authentic-sound-machine), [Yogasleep Whish](https://www.yogasleep.com/products/whish), [Sleep Foundation](https://www.sleepfoundation.org/best-white-noise-machines)

---

## 2. Architektur

```
        Handy (Home-Assistant-App)                 Music Assistant (Spotify, Radio, NAS)
                   │                                              │
            Home Assistant ◄──── MQTT (Auto-Discovery) ────┐      │ Slimproto
                                                           │      │
 ┌──────────────────────── Raspberry Pi 3 A+ ──────────────┴──────┴──────────────┐
 │  sleepgen (Python)                                       squeezelite          │
 │   ├─ Sound-Engine: 10 Klänge live erzeugt, Mixer,                │            │
 │   │  Fade-in, Sleep-Timer mit Fade-out, Limiter ─────► ALSA dmix ◄┘ (mono)     │
 │   ├─ Lampe: Farbe, Helligkeit, Sonnenaufgang, Kerze, Einschlafen              │
 │   └─ Drehknopf: Lautstärke / Sounds an-aus / Lampe                            │
 └────────────┬──────────────────────────────┬───────────────────────────────────┘
              │ I²S                          │ SPI (GPIO10)
        DigiAMP+ 35 W ──► 4"-Breitbänder     SK6812-RGBW-Ring im Lampenschirm
                          + Passivmembran
```

**Entscheidungen:**
- **Raspberry Pi (3 A+, alternativ Zero 2 W) statt ESP32**, weil nur so Musik über Music Assistant, gleichzeitiges Mischen von Sounds und Musik und ein guter Verstärker sauber gehen (Details in [HARDWARE.md](HARDWARE.md)).
- **Alle Klänge werden live berechnet** (Regen mit einzelnen Tropfen, Wellen, die anrollen und brechen, Donner mit Nachrollen, Vogelrufe). Es gibt keine Loops, die man nachts wiedererkennt, und keine Lizenzprobleme. Eigene WAV-Aufnahmen können zusätzlich eingebunden werden.
- **Home Assistant über MQTT mit Auto-Discovery:** Die Lampe legt alle Entitäten selbst an, Wecker, Sonnenaufgang und Automatik kommen über die Integration [Dusk & Dawn](DUSK_AND_DAWN.md) oder alternativ über das [Paket](../homeassistant/sleepgen_package.yaml).
- **Am Gerät nur ein Drehknopf:** Drehen = Lautstärke, Drücken = Sounds an/aus, lange Drücken = Lampe.

---

## 3. Stand

| Bereich | Stand |
|---|---|
| Sound-Engine (10 Klänge, Mixer, Timer, Fades) | fertig, getestet (`hardware/device/tests`) |
| Lampe (Farbtemperatur, RGB, Sonnenaufgang, Kerze, Einschlafen) | fertig, getestet |
| Home Assistant (MQTT-Discovery, Paket mit Aufwachlicht, Dashboard) | fertig; MQTT mit echtem Broker getestet, HA-Paket noch nicht in einer echten HA-Instanz |
| Musik (AirPlay 2, Spotify Connect, Music Assistant) | Installationsskript fertig, auf echter Hardware noch nicht getestet |
| Drehknopf, LED-Treiber, DigiAMP+ | Code fertig, braucht die echte Hardware zum Test |
| Gehäuse | OpenSCAD + STL fertig. Chassismaße vor dem Druck mit dem Datenblatt abgleichen |
| Online-Demo | veröffentlicht |

---

## 4. Bauphasen

| Phase | Ziel | Fertig wenn … |
|---|---|---|
| **1 – Teile bestellen** | Stückliste aus [HARDWARE.md](HARDWARE.md) | alles da, Chassismaße im SCAD geprüft |
| **2 – Tischaufbau** | Pi + DigiAMP+ + Lautsprecher lose verkabeln, `install.sh` laufen lassen | `aplay` spielt Meeresrauschen |
| **3 – Home Assistant** | MQTT einrichten, Paket + Dashboard einspielen | Sounds und Mischpult per Handy steuerbar |
| **4 – Licht + Knopf** | LED-Strip, Pegelwandler, Drehgeber anschließen | Sonnenaufgang läuft, Knopf regelt die Lautstärke |
| **5 – Musik** | Music Assistant einrichten | Spotify/Radio läuft auf der Lampe |
| **6 – Gehäuse** | drucken, abdichten, montieren | steht fertig am Bett |
| **7 – Extras** | eigene Automationen, eigene Aufnahmen | nach Lust und Laune |

---

## 5. Stolperfallen

- **Dichte Lautsprecherkammer:** Ohne Dichtheit arbeitet die Passivmembran nicht und der Bass fehlt.
- **SPI-Takt für LEDs:** Ohne `core_freq=250` in `/boot/firmware/config.txt` flackern die LEDs. Das Installationsskript setzt den Wert.
- **LED-Strom:** Maximal 70 % Helligkeit (Software-Limit), der Step-down muss 3 A liefern.
- **Lautstärke nachts:** Der DigiAMP+ regelt in Hardware, deshalb ist bei leiser Einstellung kein Rauschen zu hören.
- **Lizenzen:** Eingebaute Klänge sind selbst erzeugt. Eigene Aufnahmen nur aus CC0-Quellen oder selbst aufgenommen verwenden.
