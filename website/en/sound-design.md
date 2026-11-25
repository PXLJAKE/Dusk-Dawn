# How the sounds are made

The built-in sounds are not recordings. Each one is computed live: inside Home Assistant by the sound core written in Rust and, with the optional sound lamp, directly on the Raspberry Pi. Both compute the same sounds.

This has three advantages:

- **No loop.** A recording repeats at some point and the ear finds the spot. A computed sound never repeats.
- **Everything is adjustable.** Every layer has its own slider and can be mixed with all others.
- **No licensing questions**, no storage. Your own recordings still work, see [Own sounds](own-sounds.md).

## Where the sounds are computed

**As a plain integration** (normal speaker): Home Assistant computes the sounds itself and provides them as an MP3 stream that the speaker plays like internet radio. That is why Sonos and Google speakers react to sliders with a delay of 2 to 10 seconds. The sound core is prebuilt for x86_64 and aarch64 and needs about 0.5 % of one CPU core for four sounds. On other systems the integration automatically uses a slower Python version with the same sound. Own sounds are played and mixed by Home Assistant.

**With the sound lamp:** the lamp only receives commands via MQTT and computes the sounds itself on the Raspberry Pi, without delay. The lamp also stores the alarm times itself, so the alarm rings even if Home Assistant or the Wi-Fi fails.

## Building blocks

The sounds consist of two parts:

1. **A carpet of noise** that fills the room. Filters shape the noise, slow random curves move volume and filters so that nothing sounds static.
2. **Many short events** by which the ear recognises the sound, for example a single drop or an air bubble. They are scattered randomly over time, loudness and stereo image. Some of them are much louder than the rest, which sounds like closeness.

The detailed description of every sound with spectra and curves is in [SOUND_DESIGN.md on GitHub](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/docs/SOUND_DESIGN.md) (German). The code lives in [`core/`](https://github.com/PXLJAKE/Dusk-Dawn/tree/main/core) (Rust) and [`custom_components/dusk_dawn/engine/`](https://github.com/PXLJAKE/Dusk-Dawn/tree/main/custom_components/dusk_dawn/engine) (Python fallback).
