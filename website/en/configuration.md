# Configuration

Dusk & Dawn is set up entirely in the user interface. No YAML is needed.

## Create a sleep spot

A **sleep spot** connects speakers, lights and optionally a presence sensor. Create it under **Settings → Devices & services → Add integration → Dusk & Dawn**.

| Field | Meaning |
| --- | --- |
| **Name** | Name of the sleep spot, for example "Bedroom". Required and must be unique. |
| **Speakers** | Media players that play the sleep sounds (as a stream). |
| **Lights** | Lights for night light, falling-asleep dimming and sunrise. |
| **Presence sensor** | Optional presence or motion sensor for automatic start and stop. |
| **DIY Soundlampe (MQTT device ID)** | Only for a self-built [sound lamp](sound-lamp.md), for example `sleepgen`. It then plays sounds and light effects itself instead of streaming. |

## Several rooms

For every further room simply add the integration again. Every sleep spot has its own speakers, lights, scene selection, alarms and automation.

## Change settings later

Speakers, lights and sensors can be changed at any time:

- in the sidebar via the **gear icon**, or
- under **Settings → Devices & services → Dusk & Dawn → Configure**. The name can be changed there too.

## Sidebar theme

Use the **sun/moon** icon at the top right of the sidebar to switch the theme: like Home Assistant (automatic), light or dark. Each browser remembers its own choice.

## Language

The sidebar and settings dialogs are available in German and English. The sidebar follows the language of your Home Assistant profile: German if it starts with "de", English otherwise.
