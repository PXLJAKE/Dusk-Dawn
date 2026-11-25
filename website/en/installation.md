# Installation

## Requirements

- Home Assistant **2025.1** or newer.
- A speaker that shows up in Home Assistant as a **media player**, for example Sonos, Google/Nest, Music Assistant, Squeezebox or AirPlay.
- Optional: lights (`light` entities) and a presence or motion sensor.

!!! warning "Echo/Alexa does not work"
    Echo and Alexa speakers do not play custom streams and therefore cannot be used.

No own hardware is needed. The [sound lamp](sound-lamp.md) is just an optional device.

## Install via HACS

[![Open repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PXLJAKE&repository=Dusk-Dawn&category=integration)

1. Search for **Dusk & Dawn** in HACS and **Download** it. If the integration is not in the default catalogue yet: ⋮ → **Custom repositories** → `https://github.com/PXLJAKE/Dusk-Dawn`, type **Integration**.
2. **Restart** Home Assistant.
3. **Settings → Devices & services → Add integration → Dusk & Dawn** and create the first sleep spot, see [Configuration](configuration.md).

**Dusk & Dawn** then appears in the sidebar on the left.

## Updates

Every new version is published as a GitHub release. HACS then offers it as an update automatically. What changed is listed under [Changelog](changelog.md).

## Manual installation without HACS

!!! warning "Open"
    The project does not document an installation without HACS yet.

## Uninstalling

!!! warning "Open"
    The project does not document how to remove the integration (including your own recordings in the `dusk_dawn_sounds/` folder) yet.
