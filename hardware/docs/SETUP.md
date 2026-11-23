# Einrichtung: Software, Home Assistant, Musik

## 1. Raspberry Pi vorbereiten

1. Mit dem **Raspberry Pi Imager** „Raspberry Pi OS Lite (64-bit)“ auf die microSD schreiben. In den Einstellungen Hostname `soundlampe`, Benutzer, WLAN und SSH setzen.
2. Karte einsetzen, Lampe einschalten, per SSH verbinden:
   ```bash
   ssh <benutzer>@soundlampe.local
   sudo apt update && sudo apt install -y git
   git clone https://github.com/PXLJAKE/Dusk-Dawn.git
   sudo ./Dusk-Dawn/device/system/install.sh
   ```
   Das Skript installiert alles, aktiviert den DigiAMP+ und SPI für die LEDs, richtet das Mischen von Sounds und Musik ein und startet die Dienste `sleepgen` und `squeezelite`.
3. `/etc/sleepgen/config.yaml` anpassen (mindestens die MQTT-Zugangsdaten, siehe unten), dann `sudo reboot`.

Kurztest ohne Home Assistant:

```bash
amixer -c 0 sset Digital 60%                       # Lautstärke
/opt/sleepgen/venv/bin/python -m sleepgen --render /tmp/t.wav --preset Meer --seconds 20
aplay /tmp/t.wav                                   # Meeresrauschen sollte kommen
journalctl -u sleepgen -f                          # Log des Dienstes
```

## 2. Home Assistant anbinden

> **Zwei Wege:** Am einfachsten steuerst du die Lampe mit der Integration **Dusk & Dawn** ([Anleitung](DUSK_AND_DAWN.md)): nach den Schritten 1–3 Dusk & Dawn über HACS installieren und beim Einrichten die Soundlampe als DIY-Gerät wählen. Die Schritte 4 und 5 sind der Weg ohne Integration, mit eigenem Paket und Dashboard.

1. In Home Assistant die App **Mosquitto broker** installieren und starten (Einstellungen → Apps). Die Integration **MQTT** wird danach vorgeschlagen, einfach bestätigen.
2. Einen Benutzer für die Lampe anlegen (Einstellungen → Personen → Benutzer, z. B. `sleepgen`). Den Namen und das Passwort in `/etc/sleepgen/config.yaml` unter `mqtt:` eintragen, `host` ist die IP von Home Assistant.
3. `sudo systemctl restart sleepgen`. Unter Einstellungen → Geräte & Dienste → MQTT erscheint das Gerät **Soundlampe** mit allen Entitäten:

| Entität | Funktion |
|---|---|
| `switch.sleepgen_sound` | Sounds an/aus |
| `select.sleepgen_preset` | Regen, Gewitternacht, Meer, Ventilator, Brown/Pink/White Noise |
| `select.sleepgen_timer` | Sleep-Timer 15–120 min (die letzten 10 min werden ausgeblendet) |
| `number.sleepgen_layer_*` | ein Regler je Klang: rain, thunder, waves, wind, fan, white, pink, brown |
| `number.sleepgen_master` | Lautstärke der Sounds |
| `number.sleepgen_device_volume` | Gerätelautstärke (wie der Drehknopf, gilt auch für Musik) |
| `light.sleepgen_lamp` | Lampe: Helligkeit, Farbtemperatur 1800–6500 K, Farbe, Effekte *Sonnenaufgang*, *Kerze*, *Einschlafen* |
| `button.sleepgen_sunrise` | Sonnenaufgang sofort starten |
| `number.sleepgen_sunrise_minutes` | Dauer des Sonnenaufgangs |
| `switch.sleepgen_lamp_follows_timer` | Licht dimmt mit dem Sleep-Timer herunter |
| `sensor.sleepgen_timer_remaining` | Restzeit |
| `switch.sleepgen_alarm` | Wecker: an = klingelt jetzt, aus = stoppen |
| `select.sleepgen_alarm_tone` | Weckton: Glocken, Klassisch, Vogelchor |
| `number.sleepgen_alarm_minutes` | Weckdauer 1–60 min, danach hört er von selbst auf |
| `number.sleepgen_alarm_volume` | Wecklautstärke |

4. **Paket mit Wecker und Automationen:** [`hardware/homeassistant/sleepgen_package.yaml`](../homeassistant/sleepgen_package.yaml) nach `/config/packages/sleepgen.yaml` kopieren und in `configuration.yaml` eintragen:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
   Danach Home Assistant neu starten. Das Paket bringt mit:
   - **Aufwachlicht:** Weckzeit einstellen. Der Sonnenaufgang startet automatisch so, dass er zur Weckzeit fertig ist (optional nur werktags, optional mit leisem Vogelgezwitscher).
   - **Wecker:** klingelt zur Weckzeit, wenn „Wecker klingelt zur Weckzeit“ an ist. Er wird in 40 s lauter, hört nach der Weckdauer auf, ein Druck auf den Drehknopf stoppt ihn sofort.
   - **Skript „Gute Nacht“:** Preset wählen, Lampe auf warmes Licht, Sleep-Timer starten, Licht dimmt mit herunter. Eigene Aktionen, z. B. alle anderen Lichter aus, sind im Skript vorbereitet.
   - **Automatisch per Präsenzmelder:** Das Paket nutzt die Beispiel-Entitäten `binary_sensor.schlafzimmer_praesenz` (Präsenzmelder) und `light.schlafzimmer_decke` (Deckenlicht). Vor dem Einspielen per Suchen und Ersetzen durch deine eigenen ersetzen.
     - *Start:* Abends im eingestellten Zeitfenster (z. B. 21:00–03:00) ist jemand im Schlafzimmer und das Deckenlicht ist aus. Dann startet der Gute-Nacht-Sound mit dem Gute-Nacht-Timer. Ausgelöst wird beim Ausschalten des Deckenlichts oder beim Betreten des dunklen Zimmers.
     - *Stopp:* 15 Minuten lang niemand mehr im Zimmer, dann gehen Sounds und Lampe aus.
     - Einschalten mit „Sounds automatisch per Präsenzmelder“, Zeitfenster mit „Auto-Start ab/bis“ (einmalig setzen, sonst ist das Fenster leer).
   - **Sounds pausieren bei Musik** (optional)
5. **Dashboard:** Den Inhalt von [`hardware/homeassistant/dashboard.yaml`](../homeassistant/dashboard.yaml) als neue Ansicht einfügen (Dashboard → Bearbeiten → Raw-Konfigurationseditor). Damit steuerst du alles vom Handy aus, auch unterwegs über die Home-Assistant-App.

Weitere Ideen für Automationen: Lampe als Nachtlicht bei Bewegung (gedimmt rot), Kerze bei Sonnenuntergang, Gewitter-Sound bei echtem Regen draußen, Sounds aus, wenn der Wecker auf dem Handy klingelt.

## 3. Musik: AirPlay 2, Spotify Connect und Music Assistant

Das Installationsskript richtet drei Wege ein, Musik auf die Lampe zu bringen. Alle laufen gleichzeitig mit den Schlafsounds, der Drehknopf regelt die Gesamtlautstärke.

| Weg | Von wo | Wie |
|---|---|---|
| **AirPlay 2** | iPhone, iPad, Mac, Apple TV | Im Kontrollzentrum auf das AirPlay-Symbol tippen und „Soundlampe“ wählen. Mit AirPlay 2 auch zusammen mit HomePods oder anderen AirPlay-Lautsprechern (Multiroom). |
| **Spotify Connect** | Spotify-App auf Handy, PC, Tablet | In Spotify unten auf „Geräte“ tippen und „Soundlampe“ wählen. Braucht Spotify Premium. |
| **Music Assistant** | Home Assistant | Spotify, Radio, NAS, Tidal, YouTube Music … zentral aus HA, auch per Automation. |

AirPlay 2 wird beim Installieren aus dem Quellcode gebaut (shairport-sync mit nqptp). Das dauert auf dem Pi 3 A+ etwa 15 Minuten. Wer einen Weg nicht braucht, lässt ihn weg: `sudo AIRPLAY=0 SPOTIFY=0 hardware/device/system/install.sh`. Nachträglich einrichten geht mit `sudo hardware/device/system/streaming.sh`.

### Music Assistant einrichten

1. Die App **Music Assistant** installieren und starten, dann die Integration hinzufügen.
2. In Music Assistant unter Einstellungen → Player taucht **Soundlampe** automatisch auf (squeezelite/Slimproto). In Home Assistant heißt der Player dann z. B. `media_player.soundlampe`.
3. Musikquellen in Music Assistant verbinden (Spotify, Radio, NAS …). Musik und Schlafsounds laufen gleichzeitig. Der Drehknopf regelt beides.

## 4. Eigene Aufnahmen

Alle mitgelieferten Klänge werden live auf dem Pi erzeugt (keine Dateien, keine Lizenzfragen). Eigene Aufnahmen gehen zusätzlich: 16-bit-WAV auf den Pi kopieren und in `config.yaml` unter `sounds:` eintragen, z. B. `file:/home/pi/sounds/regen-am-fenster.wav`. Die Datei wird automatisch nahtlos geloopt und in der Lautstärke angeglichen. Legale Quellen: freesound.org mit Filter CC0, Pixabay oder eigene Handyaufnahmen.

## 5. Entwicklung am PC

```bash
cd device
pip install -e .[dev]
pytest                                            # 27 Tests, inkl. MQTT-Test mit lokalem mosquitto
python -m sleepgen --render demo.wav --preset Gewitternacht --seconds 60
python -m sleepgen --config config.example.yaml --no-audio -v   # läuft ohne Pi-Hardware
```
