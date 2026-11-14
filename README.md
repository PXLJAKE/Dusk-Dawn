# SleepGenerator – Soundlampe

Retro-Tischlampe fürs Bett mit eingebautem Lautsprecher: Regen, Meer, Gewitter, Wind, Kaminfeuer, Vögel, Ventilator und White/Pink/Brown Noise, frei mischbar, mit Sleep-Timer, Aufwachlicht und Musikplayer in Home Assistant.

![Soundlampe](enclosure/renders/assembly.png)

- **Online-Demo:** https://claude.ai/artifact/DLmL7VoFJZXLVwC1FM6WSx
- **Plan und Überblick:** [docs/PLAN.md](docs/PLAN.md)
- **Komponenten und Verdrahtung:** [docs/HARDWARE.md](docs/HARDWARE.md)
- **Einrichtung (Pi, Home Assistant, Music Assistant):** [docs/SETUP.md](docs/SETUP.md)
- **Gehäuse zum 3D-Druck:** [enclosure/](enclosure/README.md)

| Ordner | Inhalt |
|---|---|
| `device/` | Software für den Raspberry Pi Zero 2 W: Sound-Engine, Lampe, Drehknopf, Home Assistant (MQTT) |
| `homeassistant/` | Home-Assistant-Paket (Aufwachlicht, Gute-Nacht-Skript) und Dashboard |
| `enclosure/` | OpenSCAD-Modell, STL-Dateien, Renderbilder |
| `demo/` | Online-Demo (eine HTML-Datei, Web Audio) |
