# Druckpakete

Ein Ordner pro Variante. Jeder enthält alle STL-Dateien (schon richtig auf der Druckplatte ausgerichtet), ein Vorschaubild und ein README mit Stückzahlen, Stützen und Einstellungen für den Bambu Lab P1S, Schrauben und Stiellänge.

| | Plissee | Glocke | Kolben | Twist | Laterne |
|---|---|---|---|---|---|
| **Kugel** | [kugel-plissee](kugel-plissee/) | [kugel-glocke](kugel-glocke/) | [kugel-kolben](kugel-kolben/) | [kugel-twist](kugel-twist/) | [kugel-laterne](kugel-laterne/) |
| **Zylinder** | [zylinder-plissee](zylinder-plissee/) | [zylinder-glocke](zylinder-glocke/) | [zylinder-kolben](zylinder-kolben/) | [zylinder-twist](zylinder-twist/) | [zylinder-laterne](zylinder-laterne/) |

![Alle Varianten](../gehaeuse/renders/alle_varianten.png)

**Gleich in jedem Paket:** Sockel, Bodenplatte, Deckel, Knopf, Lichtkern. **Je nach Fuß:** der Körper. **Je nach Schirm:** Schirm, Stiel (140 mm für Plissee/Glocke, 95 mm für Kolben/Twist/Laterne), Kerndeckel und bei Plissee/Glocke die Spinne.

## Als ZIP herunterladen

Jedes Paket gibt es als fertige ZIP mit allen STL, einer Anleitung (`LIES_MICH_ZUERST.html`), der Montageanleitung als PDF und der Hardware-Liste. Sie liegen im [Release „Druckpakete“](https://github.com/PXLJAKE/Dusk-Dawn/releases/tag/druckpakete):

| | Plissee | Glocke | Kolben | Twist | Laterne |
|---|---|---|---|---|---|
| **Kugel** | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/kugel-plissee.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/kugel-glocke.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/kugel-kolben.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/kugel-twist.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/kugel-laterne.zip) |
| **Zylinder** | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/zylinder-plissee.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/zylinder-glocke.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/zylinder-kolben.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/zylinder-twist.zip) | [ZIP](https://github.com/PXLJAKE/Dusk-Dawn/releases/download/druckpakete/zylinder-laterne.zip) |

Die ZIPs werden bei jeder Änderung an `pakete/` automatisch neu gebaut (Workflow „Druckpakete“). Lokal erzeugst du sie mit `python3 hardware/gehaeuse/werkzeug/zip_bauen.py`, sie landen in `dist/druckpakete/`.

Die Pakete werden aus [`../gehaeuse/soundlampe.scad`](../gehaeuse/soundlampe.scad) erzeugt, siehe [Gehäuse-README](../gehaeuse/README.md#neu-exportieren).
