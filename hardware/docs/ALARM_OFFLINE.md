# Wecker ohne Home Assistant

Die Weckzeiten bearbeitest du wie gewohnt im Dusk-&-Dawn-Panel. Home Assistant schickt die Liste an die Soundlampe, und die Lampe **speichert sie auf der SD-Karte und klingelt selbst**. Dafür braucht sie weder Home Assistant noch Internet noch WLAN.

| Situation | Wecker |
|---|---|
| Home Assistant oder Broker ist aus | klingelt normal |
| Internet fällt aus | klingelt normal |
| WLAN/Router ist aus | klingelt normal (Lampe läuft allein) |
| Kurzer Stromausfall, Lampe startet neu | klingelt normal. Ist sie bis zu 20 Minuten nach der Weckzeit wieder da, klingelt sie sofort nach dem Start. |
| Wecker in HA geändert, während die Lampe aus war | die neue Liste kommt beim nächsten Verbinden an (retained MQTT-Nachricht) |

Die Lampe rechnet auch den Sonnenaufgang davor selbst. Ein Wecker ohne Wochentage klingelt einmal und schaltet sich dann selbst aus. Home Assistant übernimmt das.

## Uhrzeit

Der Pi hat keine Batterieuhr. Mit Internet stellt er die Zeit über NTP, ohne Internet merkt er sich die letzte Zeit und läuft ab dem Start weiter. Nach einem längeren Stromausfall ohne Netz kann die Uhr dadurch falsch gehen, und der Wecker klingelt zur falschen Zeit.

Wer den Wecker wirklich verlässlich will, steckt eine **DS3231-Batterieuhr** an (ca. 3 €, I²C: 3V3, GND, SDA = GPIO2, SCL = GPIO3) und trägt in `/boot/firmware/config.txt` ein:

```
dtparam=i2c_arm=on
dtoverlay=i2c-rtc,ds3231
```

Danach `sudo apt remove --purge fake-hwclock` (falls vorhanden) und `sudo reboot`. Mit `timedatectl` und `sudo hwclock -r` prüfst du die Zeit.

## Einstellungen

In `config.yaml` unter `alarm:` kannst du `grace_min` ändern (Standard 20). Die Weckzeiten liegen in `/var/lib/sleepgen/alarms.json`.
