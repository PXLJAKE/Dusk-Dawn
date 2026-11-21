# Dusk & Dawn – Schlafsounds, Wecker und Sonnenaufgang für Home Assistant

**Schlafgeräusche für Home Assistant:** Regen, Meer, Gewitter, Kaminfeuer, Vögel, Wind, Ventilator, White/Pink/Brown Noise, frei mischbar, mit Sleep-Timer, Lichtwecker (Sonnenaufgang) und Wecker. Läuft als HACS-Integration mit eigener Seitenleiste auf jedem Lautsprecher (Sonos, Google Nest, Music Assistant …) und mit jeder Lampe.

*Sleep sounds / white noise machine for Home Assistant: rain, ocean waves, thunderstorm, fireplace, birds, brown noise, sleep timer, sunrise alarm. HACS custom integration with sidebar panel, works with any media player and light.*

![Seitenleiste](docs/integration/desktop-alarms.png)

## Installation über HACS

1. HACS öffnen → oben rechts ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/PXLJAKE/Dusk-Dawn`, Typ **Integration**.
2. „Dusk & Dawn“ suchen, **Herunterladen**, Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Dusk & Dawn**, Schlafplatz mit Lautsprecher, Lampen und optional Präsenzmelder anlegen.

Bedienung, Entitäten, Aktionen und Grenzen: [docs/DUSK_AND_DAWN.md](docs/DUSK_AND_DAWN.md).

- **Online-Demo:** https://claude.ai/artifact/DLmL7VoFJZXLVwC1FM6WSx
- **Eigene Aufnahmen hochladen** (Regen, Meer, Wind, Vögel, Blätter, Feuer, endlos ohne hörbare Schleife): [docs/EIGENE_AUFNAHMEN.md](docs/EIGENE_AUFNAHMEN.md)
- **Sound-Design (wie die Klänge entstehen, Wecker):** [docs/SOUND_DESIGN.md](docs/SOUND_DESIGN.md)
- **Schnittstelle Integration ↔ Seitenleiste ↔ Gerät:** [docs/CONTRACT.md](docs/CONTRACT.md)

## Eigene Hardware (optional)

Wer keinen vorhandenen Lautsprecher nutzen will, baut sich die **Soundlampe**: eine Nachttischlampe mit Raspberry Pi, eingebautem Lautsprecher und LED-Lichtkern, wahlweise mit Kugel- oder Zylinderfuß und fünf Schirmen. Die Integration erkennt sie automatisch über MQTT. Musik spielt sie per **AirPlay 2**, **Spotify Connect** und über **Music Assistant**, gleichzeitig mit den Schlafgeräuschen.

![Alle Varianten](hardware/gehaeuse/renders/alle_varianten.png)

Alles dazu liegt in [`hardware/`](hardware/README.md), die fertigen Druckpakete je Variante in [`hardware/pakete/`](hardware/pakete/README.md).

## Ordner

| Ordner | Inhalt |
|---|---|
| `custom_components/dusk_dawn/` | Home-Assistant-Integration Dusk & Dawn (über HACS installierbar) |
| `core/` | Klangkern in Rust (Python-Paket `dusk_dawn_core`) |
| `tests/` | Tests der Integration |
| `docs/` | Doku zur Integration, Sound-Design, Online-Demo |
| `hardware/` | Optional: Soundlampe zum Selberbauen (Software für den Pi, Gehäuse, Druckpakete, Anleitungen) |
