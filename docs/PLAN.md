# SleepGenerator – Bauplan

Ein DIY-Soundgenerator fürs Bett: Regen, White/Pink/Brown Noise, Wellen, Gewitter, Wind usw. auswählen **und frei mischen**, mit Sleep-Timer und sanftem Ausblenden. Basis: ESP32-S3, I2S-Verstärker, ein ordentlicher Breitbandlautsprecher und ein 3D-gedrucktes Gehäuse.

---

## 1. Was gibt es schon zu kaufen?

| Gerät | Preis (ca.) | Sounds | Mischen? | Bemerkung |
|---|---|---|---|---|
| **Hatch Restore 3** | 169,99 $ (+ optional Hatch+ 4,99 $/Monat) | 60+ (Natur, Regen, Ventilator, Vögel, ASMR) | Nicht dokumentiert, man wählt einen Sound/eine Routine | Kommt deiner Idee am nächsten: Wecker + Licht + Sounds, Steuerung per App. Teuer, Teile hinter Abo. |
| **Snooz / LectroFan** | 40–90 € | Ventilator, White/Pink/Brown Noise | Nein | Sehr gutes Rauschen, aber keine Naturgeräusche. |
| **Yogasleep Dohm** | ca. 50 € | Mechanischer Lüfter | Nein | Echter Lüfter, nur ein Geräusch. |
| **Yogasleep Whish** | ca. 42 $ | Mehrere Naturklänge | Nicht angegeben | Einfaches Mehrklang-Gerät. |
| **Hammacher „Customizable 120 Authentic Sound Machine“** | eingestellt | 18 Grundsounds + Zusätze (Donner, Möwen, Vögel …) | **Ja, 120 Kombinationen** | Das einzige Gerät, das ich gefunden habe, das wirklich Ebenen mischt. Gibt es aber nicht mehr. |

**Fazit:** Der **Hatch Restore 3** ist das Gerät, das „Soundmaschine fürs Bett mit vielen Klängen“ am besten erfüllt. **Echtes Mischen mehrerer Ebenen** (z. B. Regen 60 % + Gewitter 30 % + Brown Noise 20 %) können aktuelle Geräte aber kaum. Das machen sonst nur Apps wie myNoise oder BetterSleep. Genau da lohnt sich der Selbstbau.

Quellen: [Tom's Guide – Hatch Restore 3](https://www.tomsguide.com/wellness/sleep/hatch-launches-new-phone-free-sunrise-alarm-clock-with-more-sleep-sounds-and-no-extra-cost), [Hammacher – 120 Sound Machine](https://www.hammacher.com/product/customizable-120-authentic-sound-machine), [Yogasleep Whish](https://www.yogasleep.com/products/whish), [Sleep Foundation – Best White Noise Machines](https://www.sleepfoundation.org/best-white-noise-machines)

---

## 2. Zielbild (Features)

**Muss:**
- Mehrere Klang-Ebenen gleichzeitig (mind. 4), jede mit eigener Lautstärke
- Sounds: White/Pink/Brown Noise, Regen, Wellen, Gewitter, Wind, Lagerfeuer, Ventilator
- Nahtlose Endlosschleifen (kein hörbarer „Klick“ beim Loop)
- Sleep-Timer (15/30/60/90 min, ∞) mit langsamem Fade-out
- Sanftes Einblenden beim Start
- Bedienung im Dunkeln ohne Handy (Drehknopf + Tasten/Touch)
- Kein helles Licht, keine Klickgeräusche

**Soll:**
- Web-Oberfläche im WLAN (Schieberegler pro Ebene, Presets speichern)
- Zufällige Ereignisse: Donnergrollen, einzelne Vogelrufe, Möwen, in variierenden Abständen
- Presets („Gewitternacht“, „Meer“, „Nur Brown Noise“)

**Kann (später):**
- Home Assistant Anbindung (MQTT): z. B. „Schlafmodus“ startet Sound, Licht aus
- Wecker mit sanftem Einblenden
- Warmes Nachtlicht (WS2812, gedimmt)

---

## 3. Hardware

### 3.1 Architektur

```
                ┌──────────────────────── ESP32-S3 ────────────────────────┐
 microSD ──SPI/SDMMC──► WAV-Loops lesen ─┐                                   │
                                         ├─► Mixer (Gain pro Ebene, Limiter) ─► I2S ──► MAX98357A ──► Lautsprecher
 Rausch-Generator (live berechnet) ──────┘        ▲                          │
 Zufalls-Events (Donner, Vögel) ─────────────────┘                          │
 Drehgeber / Touch ──► Bedienlogik, Timer, Fades ── WLAN-Webserver / MQTT   │
                └────────────────────────────────────────────────────────────┘
 USB-C Netzteil 5 V / 2 A ──► ESP32 + Verstärker
```

### 3.2 Bauteile

| Teil | Empfehlung | Warum |
|---|---|---|
| Mikrocontroller | **ESP32-S3-DevKitC-1 N16R8** (16 MB Flash, 8 MB PSRAM) | Zwei Kerne (Audio auf einem, WLAN/UI auf dem anderen), PSRAM für große Puffer, SDMMC-Interface |
| Verstärker | **MAX98357A** I2S-Class-D-Board (3 W an 4 Ω bei 5 V) | Digital rein, kein separater DAC nötig, billig, einfach |
| Alternative (bessere Qualität) | PCM5102A-DAC + kleiner Class-D (z. B. TPA3110/PAM8406) | Weniger Grundrauschen bei sehr leiser Nachtlautstärke |
| Lautsprecher | 3" Breitbänder, 4 oder 8 Ω, 5–10 W (z. B. **Visaton FRS 8**, Dayton CE65W/CE81) | Für Regen und Wellen zählt warmer Tiefmitteltonbereich mehr als Pegel |
| Speicher | microSD-Modul oder SD-Slot (bei S3 per SDMMC 1-bit) + 8–32 GB Karte | Platz für viele lange, hochwertige Loops |
| Bedienung | **Rotary-Encoder mit Taster** (KY-040 oder besser Alps EC11) + 2–3 kapazitive Touch-Flächen | Encoder = Lautstärke/Auswahl; Touch = lautlos, kein Klicken nachts |
| Strom | USB-C-Netzteil 5 V / 2 A, 1000 µF Elko am Verstärker | Stabile Versorgung, weniger Brummen bei WLAN-Bursts |
| Optional | 0,91" OLED (dunkel schaltend) oder nur 1 gedimmte LED, WS2812-Ring als Nachtlicht | Display nachts eher störend → nur beim Bedienen kurz an |

### 3.3 Pinbelegung (Vorschlag ESP32-S3)

| Funktion | Pin |
|---|---|
| I2S BCLK | GPIO 4 |
| I2S LRC (WS) | GPIO 5 |
| I2S DOUT | GPIO 6 |
| MAX98357A SD (Enable/Mute) | GPIO 7 |
| SD CLK / CMD / D0 (SDMMC 1-bit) | GPIO 12 / 11 / 13 |
| Encoder A / B / Taster | GPIO 15 / 16 / 17 |
| Touch 1 / 2 / 3 | GPIO 1 / 2 / 3 (Touch-fähig) |
| WS2812 (optional) | GPIO 48 (onboard) oder 18 |

**Wichtig beim MAX98357A:**
- GAIN-Pin auf niedrigste Stufe (3 dB, über 100 kΩ an GND), Lautstärke digital regeln. Sonst hört man bei leiser Nachtlautstärke das Grundrauschen.
- SD-Pin per GPIO steuern: Verstärker aus, wenn nichts spielt (kein Rauschen, weniger Strom, kein „Plopp“).

---

## 4. Sounds: Woher und wie speichern?

### 4.1 Live berechnet (prozedural), braucht keine Dateien
| Sound | Methode |
|---|---|
| White Noise | Schneller Zufallsgenerator (xorshift32) |
| Pink Noise | White Noise durch Paul-Kellet-Filter |
| Brown Noise | White Noise integriert (Leaky Integrator) + DC-Filter |
| Ventilator | Brown/Pink Noise + leichte tieffrequente Modulation (LFO) |
| Wind | Bandpass-gefiltertes Rauschen, Filterfrequenz und Pegel langsam zufällig moduliert |
| Wellen (einfach) | Rauschen mit langsamer Hüllkurve (8–12 s Periode), Tiefpass öffnet bei jeder „Welle“ |
| Regen (einfach) | Gefiltertes Rauschen + zufällige kurze „Tropfen“-Impulse |

Vorteil: unendlich lang, nie eine Wiederholung, keine Lizenzfragen. Rauschen klingt so perfekt. Wellen und Regen klingen prozedural okay, aber echte Aufnahmen sind deutlich schöner.

### 4.2 Aufnahmen (Samples) auf SD-Karte
Für Regen, Meer, Gewitter, Lagerfeuer, Vögel lieber echte Aufnahmen nehmen.

**Format:** WAV, 16 bit, mono, 32 kHz (oder 44,1 kHz). Kein Dekodieren nötig, 4 Ebenen gleichzeitig sind für die SD-Karte trivial (~64–88 KB/s pro Ebene). Optional später MP3/OGG, um Platz zu sparen.

**Nahtlose Loops vorbereiten (Audacity):**
1. 2–10 Minuten lange Aufnahme wählen (je länger, desto weniger merkt man die Wiederholung)
2. Ende und Anfang 2–3 s überlappen und crossfaden
3. Auf −3 dBFS normalisieren, gleiche Lautheit für alle Loops (z. B. −23 LUFS), damit der Mixer vorhersehbar ist
4. Mono, 32 kHz, 16 bit exportieren

**Zufalls-Events (Donner, Vögel):** Kurze Einzelclips (5–20 s), die der Mixer in zufälligen Abständen mit zufälliger Lautstärke abspielt. So wirkt ein Gewitter lebendig statt geloopt.

### 4.3 Lizenzen (wichtig!)
Keine Sounds aus Apps oder YouTube rippen. Gute legale Quellen:
- **freesound.org**, Filter auf **CC0** (keine Namensnennung nötig) oder CC-BY (Namensnennung in `sounds/CREDITS.md`)
- **Pixabay Sound Effects** (Pixabay-Lizenz, frei nutzbar)
- **BBC Sound Effects** (RemArc-Lizenz: privat/nicht-kommerziell ok, nicht öffentlich weiterverteilen)
- **Selbst aufnehmen** (Handy reicht für Regen am Fenster)

Die Sounddateien kommen **nicht** ins Git-Repo (Größe + Lizenz), sondern nur eine Liste mit Quellen und ein Skript zum Konvertieren.

---

## 5. Software

### 5.1 Stack
- **PlatformIO + Arduino-ESP32** (schneller Einstieg) mit der Bibliothek **arduino-audio-tools** (pschatzmann): kann I2S, WAV/MP3 von SD, Mischen, Lautstärke
- Alternativ ESP-IDF + ESP-ADF, wenn es später professioneller werden soll

### 5.2 Audio-Pipeline
- Feste Abtastrate 32 kHz, mono, intern 32-bit-Integer oder float
- **Audio-Task auf Core 1** mit hoher Priorität, WLAN/Web/UI auf Core 0
- Pro Ebene: Quelle (Rauschen / WAV-Loop / Event-Player) → Gain (geglättet, keine Sprünge) → Summe
- Summe → Master-Lautstärke (logarithmische Kurve) → **Soft-Limiter** (damit 4 laute Ebenen nicht übersteuern) → I2S
- DMA-Puffer großzügig (z. B. 8 × 512 Samples), damit WLAN-Aktivität keine Aussetzer verursacht

### 5.3 Datenmodell
```jsonc
// /presets/gewitternacht.json
{
  "name": "Gewitternacht",
  "layers": [
    { "source": "sd:/loops/rain_heavy.wav", "gain": 0.7 },
    { "source": "gen:brown",                "gain": 0.2 },
    { "source": "sd:/loops/wind_soft.wav",  "gain": 0.25 }
  ],
  "events": [
    { "dir": "sd:/events/thunder/", "gain": [0.3, 0.8], "every_s": [40, 180] }
  ]
}
```
Presets in LittleFS oder auf der SD-Karte, letzter Zustand in NVS (beim Einschalten weiterspielen).

### 5.4 Bedienkonzept (ohne Handy)
| Aktion | Wirkung |
|---|---|
| Encoder drehen | Lautstärke |
| Encoder drücken | Play/Pause (mit Fade) |
| Encoder lang drücken + drehen | Preset wechseln |
| Touch 1 | Sleep-Timer durchschalten (15 → 30 → 60 → 90 → ∞), per kurzem Ton/LED-Blinken bestätigt |
| Touch 2 | Nächstes Preset |
| Touch 3 (optional) | Nachtlicht an/aus |

**Fade-out:** über die letzten 5–10 min exponentiell leiser werden (klingt natürlicher als linear), danach Verstärker aus.

### 5.5 Web-UI
- ESP32 im Heim-WLAN (WiFiManager für Erstkonfiguration), erreichbar unter `http://sleepgen.local` (mDNS)
- Eine Seite: pro Ebene Dropdown + Schieberegler, Timer, Presets speichern/laden, Sounds hochladen
- Updates per WebSocket, damit die Regler sofort reagieren
- OTA-Firmware-Update

### 5.6 Home Assistant (später)
MQTT mit Auto-Discovery: Entitäten für Play/Pause, Lautstärke, Preset, Timer. Dann geht z. B. „Gute Nacht“-Szene → Licht aus + Sound „Regen“ + Timer 60 min.

---

## 6. Gehäuse (3D-Druck)

- **Form:** geschlossene Box oder Zylinder, ca. **0,8–1,5 Liter** Innenvolumen für einen 3"-Treiber (mehr Volumen = mehr Bass, wichtig für Wellen/Brown Noise)
- **Material:** PETG oder PLA, **3 mm Wände, 4–5 Perimeter, 30–40 % Infill** → wenig Mitschwingen
- **Dämmung:** Innen Polyesterwatte oder Noppenschaum, damit es nicht „boxig“ klingt
- **Lautsprecher:** von vorne mit Dichtung (Moosgummi) und M3-Gewindeeinsätzen verschraubt, davor Gitter (gedruckt, ≥ 60 % offen) oder Stoff
- **Elektronik:** getrennte Kammer oder Halterung auf Abstandsbolzen, USB-C-Buchse hinten (Panel-Mount), SD-Slot von außen zugänglich
- **Bedienung:** Encoder oben, Touch-Flächen als Kupferfolie innen unter 1–2 mm Deckel (unsichtbar, lautlos)
- **Füße:** Gummifüße, damit der Nachttisch nicht mitbrummt
- **Optional:** Bassreflexrohr (mit Rechner wie WinISD auslegen), Diffusor oben für das Nachtlicht
- **CAD:** Fusion 360, Onshape oder OpenSCAD (parametrisch, gut fürs Repo)

---

## 7. Stückliste (grob, Stand 11/2026)

| Teil | Preis (ca.) |
|---|---|
| ESP32-S3-DevKitC-1 N16R8 | 10–15 € |
| MAX98357A I2S-Verstärker | 4–7 € |
| 3"-Breitbandlautsprecher (Visaton FRS 8 / Dayton) | 12–20 € |
| microSD-Modul + 16 GB Karte | 6–8 € |
| Rotary-Encoder EC11 + Knopf | 3–5 € |
| Kupferfolie für Touch, Kleinteile, Elko, Kabel | 5 € |
| USB-C-Buchse (Panel) + Netzteil 5 V/2 A | 8–12 € |
| Gewindeeinsätze M3, Schrauben, Gummifüße, Dämmwatte | 6–8 € |
| Filament (~250 g PETG) | 5 € |
| **Summe** | **ca. 60–85 €** |

Optional: OLED 0,91" (4 €), WS2812-Ring (4 €), PCM5102A-DAC + besserer Amp (10–15 €).

---

## 8. Phasen

| Phase | Ziel | Fertig wenn … |
|---|---|---|
| **0 – Breadboard** | ESP32-S3 + MAX98357A + Lautsprecher verkabeln, Sinuston ausgeben | Ton kommt sauber raus |
| **1 – Rauschen** | White/Pink/Brown Noise live erzeugen, Lautstärke per Encoder | Die Kiste ist schon ein brauchbarer Noise-Generator |
| **2 – SD-Loops** | WAV von SD nahtlos loopen, erste Sounds vorbereiten (Audacity, CC0) | Regen läuft 1 h ohne Klick oder Aussetzer |
| **3 – Mixer** | 4 Ebenen + Gain + Limiter + Zufalls-Events (Donner) | „Gewitternacht“ klingt lebendig |
| **4 – Bedienung** | Encoder + Touch, Timer, Fade-in/out, Zustand merken | Ohne Handy voll bedienbar |
| **5 – Web-UI** | WLAN, Schieberegler, Presets, Upload, OTA | Mischen vom Handy aus |
| **6 – Gehäuse** | CAD, Probedruck, Akustik testen, Dämmung | Steht fertig am Bett |
| **7 – Extras** | Home Assistant/MQTT, Wecker, Nachtlicht | Nach Lust und Laune |

Phase 0–1 ist an einem Abend machbar, 2–4 an einem Wochenende, 5–6 je ein weiteres Wochenende.

---

## 9. Stolperfallen

- **WLAN-Störgeräusche:** WLAN-Sendebursts können als leises Ticken hörbar werden. Gegenmittel: Elko am Verstärker, kurze Leitungen, Masse sternförmig, nachts optional WLAN in Modem-Sleep oder ganz aus.
- **Grundrauschen bei leiser Lautstärke:** MAX98357A-Gain niedrig, digital nicht unter ~10 % gehen, sonst besseren DAC nehmen.
- **Loop-Klicks:** immer an Nulldurchgängen schneiden bzw. crossfaden.
- **Lautstärkesprünge:** alle Gain-Änderungen über ~50 ms glätten.
- **Licht:** jede LED nachts mit Tape/Diffusor abdunkeln oder per Software aus.
- **Lizenzen:** nur CC0/eigene Aufnahmen weitergeben, Credits pflegen.

---

## 10. Repo-Struktur (geplant)

```
SleepGenerator/
├── docs/PLAN.md          ← dieses Dokument
├── firmware/             ← PlatformIO-Projekt (ESP32-S3)
├── web/                  ← Web-UI (wird ins LittleFS geflasht)
├── enclosure/            ← CAD-Dateien (OpenSCAD/STEP/STL)
└── sounds/
    ├── CREDITS.md        ← Quellen + Lizenzen der Sounds
    └── prepare.sh        ← ffmpeg: in 32 kHz mono WAV konvertieren
```
