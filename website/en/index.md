# Dusk & Dawn

**Dusk & Dawn** turns any speaker and any light in Home Assistant into a sleep aid with an alarm clock. Rain, ocean, wind, thunder, fan and white/pink/brown noise can be mixed freely, plus your own recordings, your own scenes, a sleep timer, a sunrise alarm and presence-based automation. Everything is controlled from its own sidebar panel. No helpers, scripts or YAML needed.

![Dusk & Dawn sidebar](assets/img/desktop-alarms.png)

## What it does

- **Mix sounds:** eight built-in sounds, each with its own level, saved as scenes. The sounds are computed inside Home Assistant (sound core in Rust, prebuilt for x86_64 and aarch64) and streamed to the speaker. No audio files are shipped and nothing repeats audibly.
- **Own sounds:** upload and name as many recordings as you like, see [Own sounds](own-sounds.md).
- **Sleep timer** with a gentle fade-out and an **alarm clock** with several alarm times, weekdays, alarm tone and a sunrise before it.
- **Light:** sunrise, falling-asleep light, colour, colour gradient and candle flicker on any light.
- **Automation:** start when someone has been in the room for at least 10 minutes, or by time window; stop when nobody is there any more; pause while music plays.
- **Several rooms:** every sleep spot has its own speaker, lights and settings.

## Get started

1. [Check the requirements and install](installation.md)
2. [Set up a sleep spot](configuration.md)
3. [Get to know the sidebar](usage.md)

Questions and problems: [FAQ](faq.md) and [Troubleshooting](troubleshooting.md).

## Optional: the sound lamp

The integration works entirely without your own hardware. If you like, you can also build the [sound lamp](sound-lamp.md), a bedside lamp with a Raspberry Pi, built-in speaker and LED light core.

## Licence and source code

Dusk & Dawn is released under the [MIT licence](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/LICENSE). Source code, issues and releases: [github.com/PXLJAKE/Dusk-Dawn](https://github.com/PXLJAKE/Dusk-Dawn).
