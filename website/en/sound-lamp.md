# Sound lamp (optional)

The integration works entirely without your own hardware. If you like, you can also build the **sound lamp**: a bedside lamp with a Raspberry Pi, built-in speaker and LED light core, with a sphere or cylinder base and five shades to choose from.

## What is different from a normal speaker

- The sounds are computed **directly on the Raspberry Pi**, without stream delay.
- The **alarm rings even** if Home Assistant or the Wi-Fi fails.
- The lamp plays music via **AirPlay 2**, **Spotify Connect** and **Music Assistant**, at the same time as the sleep sounds.
- Home Assistant finds the lamp via **MQTT**. When you create the sleep spot, enter its MQTT device ID, see [Configuration](configuration.md).
- Own sounds from the sidebar do not run on the lamp, see [Own sounds](own-sounds.md#with-the-diy-sound-lamp).

## Build and set up

The hardware documentation lives in the repository and is written in German:

| Step | Guide |
| --- | --- |
| Overview | [hardware/README.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/README.md) |
| Choose a variant and print | [Print packages](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/pakete/README.md) |
| Buy parts | [HARDWARE.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/HARDWARE.md) |
| Assemble | [Assembly guide (PDF)](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/pdf/Soundlampe_Montageanleitung.pdf), [Build guide (PDF)](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/pdf/Soundlampe_Bauanleitung.pdf) |
| Set up Raspberry Pi and Home Assistant | [SETUP.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/SETUP.md) |
| Alarm without Home Assistant | [ALARM_OFFLINE.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/ALARM_OFFLINE.md) |
| Software for the Pi | [hardware/device/](https://github.com/PXLJAKE/Dusk-Dawn/tree/main/hardware/device) |

!!! warning "Open: software updates on the lamp"
    The lamp software is not updated through HACS. New features such as the volume curve from version 0.3.5 on need an update on the Pi. The hardware documentation does not have a step-by-step guide for this yet.
