# Troubleshooting

Most hints are in the Home Assistant log: **Settings → System → Logs**, filter for "dusk_dawn".

## More detail in the log

For more detailed messages you can enable debug logging for the integration: **Settings → Devices & services → Dusk & Dawn → Enable debug logging**. Alternatively in `configuration.yaml` via the [logger integration](https://www.home-assistant.io/integrations/logger/):

```yaml
logger:
  logs:
    custom_components.dusk_dawn: debug
```

## The speaker plays nothing

**The log says "No internal URL available; set one under Settings > System > Network".**
The speaker fetches the stream from Home Assistant's internal URL. Set it under **Settings → System → Network**.

**The log says "Cannot start ffmpeg".**
The sounds are encoded to MP3 with ffmpeg. Dusk & Dawn uses the ffmpeg configured in Home Assistant (integration *FFmpeg*), otherwise the `ffmpeg` command. Check that ffmpeg is available on your system.

**The log says "Encoder for … ended unexpectedly".**
The encoder stopped during playback.

!!! warning "Open"
    Causes and fixes for "Encoder … ended unexpectedly" are not documented in the project yet.

**The speaker is an Echo/Alexa.**
These devices do not play custom streams, see [FAQ](faq.md#which-speakers-work).

## The lights do not react

The log then shows a message such as "light.turn_on failed for …" with the light's error. Check whether the light can be switched directly in Home Assistant and whether it is selected in the sleep spot ([Configuration](configuration.md)).

## The sound lamp does not react

**The log says "MQTT is not set up; the DIY lamp … cannot be controlled".**
The sound lamp is controlled via MQTT. Set up the MQTT integration and a broker as described in [SETUP.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/hardware/docs/SETUP.md) (German), and check the MQTT device ID of the sleep spot.

## Uploading own recordings fails

| Message | Cause |
| --- | --- |
| admin required | Only administrators may upload recordings. |
| file too large (max 400 MB) | The file is larger than 400 MB. |
| too short (… s, at least 3 s) | The recording is shorter than 3 seconds. |

Other messages usually come from ffmpeg when it cannot read the file.

## Which sound core is running?

On start, Dusk & Dawn writes to the log whether the Rust sound core ("uses the Rust sound engine") or the slower Python version ("uses the Python sound engine") is running. The Python version sounds the same but needs more CPU.

## The sidebar shows the old version after an update

The sidebar's URL contains the version and modification time, so the browser loads the new file after an update. Reload the page once. The sidebar reports its version in the browser console.

!!! warning "Open"
    Hints for installations behind a proxy or CDN that caches static files are not documented in the project yet.

## Report a bug

If none of this helps, please report the bug as an [issue on GitHub](https://github.com/PXLJAKE/Dusk-Dawn/issues) with your Home Assistant version, speaker type and the relevant log lines.
