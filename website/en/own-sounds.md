# Own sounds

In addition to the eight built-in, computed sounds you can create **as many own sounds as you like**, name them and fill them with your own recordings (phone, voice recorder, free sound archives). An own sound appears in the mixer like any other, can be mixed into scenes and plays endlessly without an audible loop. The longer the recording, the better: from about 5 minutes on it no longer sounds like a loop.

## How it works

1. Sidebar **Dusk & Dawn → Sounds**, card **My sounds**.
2. Enter a name (for example "Rain on the tent" or "Forest brook") and **Create sound**. You can rename it at any time.
3. On the sound, **Add recording**. Only administrators may upload.
4. The sound shows up in the group **Mine** in the mixer. Sliders, scenes, timer and volume work as for the built-in sounds.

## Files

| What | Limit |
| --- | --- |
| Formats | anything ffmpeg can read: WAV, MP3, FLAC, OGG, M4A, AAC, even video (only the audio is used) |
| Size | up to 400 MB per file |
| Length | at least 3 seconds, 5 minutes or more recommended |
| Count | up to 12 files per sound, they take turns |
| Location | Home Assistant folder `dusk_dawn_sounds/`, shared by all sleep spots |

!!! note "Backup"
    The recordings are not part of the integration's backup. Please back up the `dusk_dawn_sounds/` folder yourself.

Deleting a sound also deletes its files and removes it from all scenes.

## How the repetition is hidden

- On upload every file is decoded to mono once and brought to a uniform loudness, so it is neither louder nor quieter than the computed sounds.
- Playback is a chain of random excerpts (45 to 150 seconds) with 6-second crossfades without a level dip. Start and length differ every time, several files take turns.
- A slow volume drift of ±1.2 dB over almost a minute keeps the sound from feeling static.

## Recording tips

- Do not point the microphone into the wind, avoid handling noise, talking or cars in the background.
- For rain and ocean, prefer distance in mono over closeness in stereo.
- Birds need a quiet spot without traffic, otherwise you hear the hum in every loop.

## With the DIY sound lamp

Own sounds from the sidebar are played by Home Assistant, so they do not run on the sound lamp. On the lamp itself an entry in `config.yaml` such as `rain=file:/home/admin/sounds/regen` replaces the computed sound with a file or a folder with several files. `file:/path/to/file.mp3` adds an extra layer. There is no upload from the sidebar to the lamp.

## Note on version 0.3.0

If you uploaded recordings for rain, ocean and so on in version 0.3.0, you will find them after the update as own sounds "… (eigene Aufnahme)". Brook, birds, leaves and fire are no longer built-in sounds, only available as your own recording.
