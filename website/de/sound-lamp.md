# Soundlampe (optional)

Die Integration funktioniert komplett ohne eigene Hardware. Wer will, baut sich zusätzlich die **Soundlampe**: eine Nachttischlampe mit Raspberry Pi, eingebautem Lautsprecher und LED-Lichtkern, wahlweise mit Kugel- oder Zylinderfuß und fünf Schirmen.

## Was anders ist als bei einem normalen Lautsprecher

- Die Klänge werden **direkt auf dem Raspberry Pi** berechnet, ohne Stream-Verzögerung.
- Der **Wecker klingelt auch**, wenn Home Assistant oder das WLAN ausfällt.
- Musik spielt die Lampe per **AirPlay 2**, **Spotify Connect** und **Music Assistant**, gleichzeitig mit den Schlafgeräuschen.
- Home Assistant erkennt die Lampe über **MQTT**. Beim Anlegen des Schlafplatzes trägst du ihre MQTT-Geräte-ID ein, siehe [Konfiguration](configuration.md).
- Eigene Klänge aus der Seitenleiste laufen nicht auf der Lampe, siehe [Eigene Klänge](own-sounds.md#mit-der-diy-soundlampe).

## Bauen und einrichten

Die Hardware-Doku liegt im Repository:

| Schritt | Anleitung |
| --- | --- |
| Übersicht | [hardware/README.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/README.md) |
| Variante wählen und drucken | [Druckpakete](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/pakete/README.md) |
| Teile kaufen | [HARDWARE.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/HARDWARE.md) |
| Zusammenbauen | [Montageanleitung (PDF)](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/pdf/Soundlampe_Montageanleitung.pdf), [Bauanleitung (PDF)](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/pdf/Soundlampe_Bauanleitung.pdf) |
| Raspberry Pi und Home Assistant einrichten | [SETUP.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/SETUP.md) |
| Wecker ohne Home Assistant | [ALARM_OFFLINE.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/ALARM_OFFLINE.md) |
| Software für den Pi | [hardware/device/](https://github.com/PXLJAKE/Dusk-Dawn/tree/main/hardware/device) |

!!! warning "Offen: Software-Updates auf der Lampe"
    Die Lampen-Software wird nicht über HACS aktualisiert. Neue Funktionen wie die Lautstärke-Kurve ab Version 0.3.5 brauchen ein Update auf dem Pi. Eine Schritt-für-Schritt-Anleitung dafür gibt es in der Hardware-Doku bisher nicht.
