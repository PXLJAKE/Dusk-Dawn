# Sidebar

After setup, **Dusk & Dawn** appears on the left in Home Assistant. The sidebar has several sections.

![Sounds in the sidebar](assets/img/desktop-sounds.png)

## Now

Start and stop, volume, sleep timer, light and your scenes to tap.

![Now view on a phone](assets/img/mobile-now.png){ width="320" }

## Scenes

A scene starts sounds (your own ones too) and can also set **volume**, **sleep timer** and **light**. For the light there is:

- Off
- White
- Colour
- Gradient, for example from orange to dark violet over 30 minutes. Brightness 0 at the end turns the light off.
- Candle
- Sleep light: warm, dimmed light that goes out with the sleep timer

Your own scenes are always at the top and can be reordered by drag and drop on the handle (or with the arrow keys). The bundled scenes such as **Good night** are suggestions: you can edit, remove and restore them.

## Sounds

Tap a scene, or set every sound individually in the **mixer** and save it as your own scene. Eight sounds are built in:

Rain, ocean, wind, thunder, fan, white noise, pink noise and brown noise.

The group **Mine** shows your own sounds, see [Own sounds](own-sounds.md).

## Sleep timer

The sleep timer fades the sounds out gently at the end, over the last 10 minutes at most. The **Sleep timer** entity offers Off, 15, 30, 45, 60 and 90 minutes. A sleep timer that is switched off stays off, even when the automation starts.

## Alarms

As many alarm times as you like, with:

- weekdays
- alarm tone **Bells** or **Classic**, with preview
- duration and volume
- sunrise on the lights before it

## Automation

The automation starts the chosen evening scene (default "Good night") within a time window. Two modes:

- **With presence sensor:** starts only once someone has been in the room for at least 10 minutes (adjustable). Off when nobody is there any more.
- **Time window only:** no sensor, start at the beginning and stop at the end of the window.

While music plays on the speaker, the automation pauses.

## Volume

The sounds are deliberately quieter than music via AirPlay or Music Assistant:

- The slider at the top equals −18 dB.
- At 50 % it is about −38 dB.
- The alarm is attenuated by another 12 dB.

With the DIY sound lamp the lamp computes this curve itself. It needs the current update of the lamp software for that.

## Gear and theme

- **Gear:** change speakers, lights and sensors, see [Configuration](configuration.md).
- **Sun/moon at the top right:** switch the theme.
