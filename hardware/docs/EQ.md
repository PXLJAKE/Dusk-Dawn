# EQ für die Soundlampe (optional)

Ein kleiner 4"-Breitbänder in einer 2-Liter-Kammer profitiert von einem leichten EQ. Der wichtigste Teil ist ein **Hochpass**, der den Konus bei Gewitter und Brown Noise vor zu viel Hub schützt. Dazu kommt eine kleine Absenkung bei 6 kHz, wo Alu-Konen zischen.

> **Stand:** Die Werte sind vorsichtig geschätzt und **nicht an der fertigen Lampe gemessen**. Das Skript wurde noch nicht auf echter Hardware getestet. Wer es einschaltet, stellt nach Gehör oder Messung nach.

## Einschalten

```bash
sudo EQ=1 ./hardware/device/system/install.sh
```

Das lädt [CamillaDSP](https://github.com/HEnquist/camilladsp), richtet eine virtuelle Soundkarte (`snd-aloop`) ein und leitet alles (Sleep Sounds, Music Assistant, AirPlay, Spotify) durch den EQ auf die DigiAMP+. Danach neu starten.

## Profile umschalten

```bash
sudo sleepgen-eq schlaf     # Standard: Hochpass 65 Hz, Zischen -3 dB, Höhen -3 dB, +1,5 dB Wärme bei 120 Hz
sudo sleepgen-eq neutral    # Hochpass 60 Hz, Zischen -2 dB, sonst flach
sudo sleepgen-eq musik      # Hochpass 60 Hz, Zischen -2,5 dB, +2,5 dB Bass-Wärme
sudo sleepgen-eq aus        # ohne EQ, direkt auf die DigiAMP+ (Notausgang)
```

Wiedergaben danach einmal neu starten.

## Eigene Werte

Die Profile liegen in `/etc/camilladsp/profiles/*.yml` (Vorlagen: `hardware/device/system/camilladsp/`). Nach dem Ändern prüfen mit `camilladsp -c <datei>` und `sudo systemctl restart camilladsp`.

## Messen (empfohlen)

Mit einem USB-Messmikro (z. B. UMIK-1) oder dem Handy-Mikrofon und der kostenlosen App REW den Frequenzgang aus 30 cm vor dem Breitbänder messen, dann die drei Filter (`hochpass`, `zisch_weg`, `waerme`) anpassen. Die Kammer und die Passivmembran verändern den Bass stärker, als man schätzt.
