# FAQ

## Do I need my own hardware?

No. Dusk & Dawn runs with any speaker that shows up in Home Assistant as a media player, and any light. The [sound lamp](sound-lamp.md) is just an optional device.

## Which speakers work?

All that show up in Home Assistant as a media player and can play a stream, for example Sonos, Google/Nest, Music Assistant, Squeezebox or AirPlay. Echo/Alexa speakers do not play custom streams and therefore do not work.

## Why does my speaker react to the sliders with a delay?

Home Assistant sends the sounds as an MP3 stream that the speaker buffers like internet radio. With Sonos and Google speakers a change therefore takes 2 to 10 seconds. The sound lamp computes the sounds itself and has no such delay.

## Why are the sounds quieter than my music?

On purpose. The slider at the top equals −18 dB, at 50 % it is about −38 dB. The alarm is attenuated by another 12 dB. See [Volume](usage.md#volume).

## Do the sounds keep playing after Home Assistant restarts?

No. After a restart of Home Assistant the sounds do not resume automatically.

## Does the alarm ring if Home Assistant or the Wi-Fi fails?

Not with a normal speaker, because the sound comes from Home Assistant. The [sound lamp](sound-lamp.md) stores the alarm times itself and rings without Home Assistant and Wi-Fi too.

## Why does the candle flicker so slowly on my light?

To avoid overloading the Zigbee network, candle flicker on normal lights is only a gentle sway with at most one command per second.

## How much CPU does it need?

The Rust sound core needs about 0.5 % of one CPU core for four sounds. It is prebuilt for x86_64 and aarch64. On other systems the integration uses a slower Python version with the same sound.

## Are my own recordings backed up?

Not with the integration's backup. They live in the Home Assistant folder `dusk_dawn_sounds/`, which you should back up yourself. See [Own sounds](own-sounds.md).

## Can I control several rooms?

Yes. Every sleep spot has its own speakers, lights and settings. Simply add the integration again for each room.

## Where did fire, birds and brook go?

These sounds are no longer built in. If you want them, upload your own recording, see [Own sounds](own-sounds.md).

## Which licence does the project use?

[MIT licence](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/LICENSE).
