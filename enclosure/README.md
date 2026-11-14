# Gehäuse: Retro-Soundlampe

![Ansicht](renders/assembly.png)

Parametrisches OpenSCAD-Modell: [`soundlampe.scad`](soundlampe.scad). Fertige STL-Dateien liegen in [`stl/`](stl/).

- **Fuß (Ø 190 × 160 mm):** Unten ein Elektronikfach, darüber eine dichte Lautsprecherkammer mit ca. 2,6 l. Vorne sitzt der 4"-Breitbänder, hinten die Passivmembran, beide hinter senkrechten Lamellen im Stil alter Röhrenradios. Oben auf dem Deckel sitzt der Drehknopf.
- **Stiel:** Messingrohr 20 mm oder gedruckt. Das LED-Kabel läuft innen durch.
- **Lichtkern:** Eine Spule (Ø 40 mm), um die der SK6812-Strip spiralförmig gewickelt wird. 0,5 m ergeben 4 Windungen.
- **Schirm (Ø 210 → 128 mm, 155 mm hoch):** Plissee-Kegel aus 40 Falten, im Vasenmodus gedruckt. Er ruht auf einem Ring (Spinne), der auf dem Stift des Kerndeckels sitzt.
- **Gesamthöhe:** ca. 41 cm

![Ansichten](renders/sheet_views.png)

![Schnitte](renders/sheet_sections.png)

Einzelbilder liegen in [`renders/`](renders/). Neu rendern: `openscad -D 'part="section_side"' -o renders/section_side.png soundlampe.scad` (Teile: `section_side`, `section_front`, `section_chamber`, `section_electronics`, `exploded`, `cutaway`).

## Teile und Druckeinstellungen

| Teil | Datei | Material | Hinweise |
|---|---|---|---|
| Fußgehäuse | `base_shell.stl` | PETG | aufrecht, 4 Wände, 25 % Gyroid, keine Stützen (Lamellen-Enden und Ausschnitte sind druckbar geformt). Mindestens 200 × 200 mm Druckbett |
| Zwischenboden | `divider.stl` | PETG | flach |
| Deckel | `top_lid.stl` | PETG | auf dem Kopf drucken (Fase unten) |
| Kabelrohr | `conduit.stl` | PETG | aufrecht |
| Bodenplatte | `bottom_plate.stl` | PETG | flach |
| Stiel | `stem.stl` | PETG | nur wenn kein Messingrohr |
| Lichtkern | `led_core.stl` | PETG | aufrecht |
| Kerndeckel | `core_cap.stl` | PETG | aufrecht |
| Spinne | `spider.stl` | PETG/PLA | flach |
| Schirm | `shade.stl` | **transluzentes** PLA/PETG (Natur, Elfenbein) | **Vasenmodus**, 0 Bodenschichten, 0,8 mm Linienbreite, Ø 210 mm passt auf 220er-Betten |
| Knopf | `knob.stl` | PLA/PETG | aufrecht. Hell oder Messingfarbe sieht retro aus |

STL neu erzeugen, z. B. nach geänderten Lautsprechermaßen:

```bash
for p in base_shell divider top_lid conduit bottom_plate stem led_core core_cap spider shade knob; do
  openscad -D "part=\"$p\"" -o stl/$p.stl soundlampe.scad
done
```

**Vor dem Druck prüfen:** Die Maße der Chassis (`drv_*`, `pr_*`) stammen nicht aus einem Datenblatt. Bitte mit dem gekauften Lautsprecher vergleichen: Flanschdurchmesser, Ausschnitt, Lochkreis und Einbautiefe (max. ca. 55 mm, sonst stößt der Magnet an das Kabelrohr).

## Zusammenbau

1. Gewindeeinsätze setzen: 4 × in die Dome für die Bodenplatte und 4 + 4 × in die Schallwände für die Chassis-Schrauben. Für den Zwischenboden den Zwischenboden selbst als Bohrschablone auf den unteren Ring legen, 6 Löcher mit 4 mm vorbohren und Einsätze setzen. Alternativ den Zwischenboden nur einkleben und mit Silikon abdichten.
2. Breitbänder von innen auf die vordere Schallwand schrauben, Passivmembran auf die hintere. Flansche jeweils mit Moosgummi abdichten.
3. Lautsprecherkabel und Kabelrohr durch den Zwischenboden führen. Zwischenboden mit Dichtband einsetzen und verschrauben, Durchführungen mit Silikon schließen.
4. Polyesterwatte locker in die Kammer legen, Breitbänder und Membran frei lassen.
5. Drehgeber in den Deckel schrauben. Oben seitlich ein 4-mm-Loch ins Kabelrohr bohren und die Drehgeber-Kabel dort hinein, das LED-Kabel von oben durch das Rohr nach unten führen. Deckel mit Dichtband aufsetzen, Rohrenden abdichten.
6. Unten: Den Pi Zero auf die 4 kurzen Dome schrauben, an den beiden Stiftleisten-Löchern 11-mm-Abstandsbolzen (M2,5) aufsetzen und den DigiAMP+ obendrauf stecken. Er liegt auf den Bolzen und den zwei hohen Domen auf. Step-down aufschrauben, DC-Buchse einsetzen, alles verdrahten (siehe [HARDWARE.md](../docs/HARDWARE.md)).
7. Stiel in den Deckel stecken (bei Bedarf einkleben). Den LED-Strip spiralförmig um den Lichtkern kleben, Kern auf den Stiel stecken, Kerndeckel aufsetzen.
8. Spinne auf den Stift setzen und den Schirm von oben darüberstülpen.
