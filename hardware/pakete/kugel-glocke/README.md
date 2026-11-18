# Paket: Kugel mit Schirm Glocke

![Vorschau](vorschau.png)

Alles, was du für diese Variante druckst, liegt in diesem Ordner. Die STL-Dateien sind schon richtig auf der Druckplatte ausgerichtet, einfach in Bambu Studio laden.

Schirm: **Glocke**, geschwungen, hängt an der Spinne. Stiel: **140 mm**.

## Druckteile

| Datei | Anzahl | Teil | Filament | Stützen | Hinweis |
|---|---|---|---|---|---|
| `01_koerper_kugel.stl` | 1 | Körper (Kugel) | Gehäusefarbe | **Tree Supports (manuell)**: nur die Decke der Knopfmulde anmalen | liegt richtig herum, Flansch auf der Platte |
| `02_sockel.stl` | 1 | Sockel | Gehäusefarbe | keine | steht kopfüber (Decke auf der Platte) |
| `03_bodenplatte.stl` | 1 | Bodenplatte | Gehäusefarbe | keine |  |
| `04_deckel.stl` | 1 | Deckel (Bajonett) | Gehäusefarbe | keine | Oberseite nach oben |
| `05_knopf.stl` | 1 | Drehknopf | Akzentfarbe | keine | Rückseite auf der Platte |
| `06_stiel_140mm.stl` | 1 | Stiel 140 mm | Akzent oder Messing | keine | oder Messingrohr Ø 20 mm außen, ≥ 13 mm innen, 140 mm lang |
| `07_lichtkern.stl` | 1 | Lichtkern | Weiß | keine | kopfüber, die kleine Brücke im Boden druckt frei |
| `08_kerndeckel.stl` | 1 | Kerndeckel | Weiß | keine | flach auf der Platte, Stift nach oben |
| `09_spinne.stl` | 1 | Spinne (Schirmhalter) | Schirmfarbe | keine |  |
| `10_schirm_glocke.stl` | 1 | Schirm Glocke | Weiß/Natur, lichtdurchlässig | keine | 3 Wände, 0 % Füllung, keine obere/untere Deckschicht nötig (Schirm ist offen) |

### Einstellungen (Bambu Lab P1S, 0,4-mm-Düse)

- **Gehäuseteile** (Körper, Sockel, Platte, Deckel, Knopf): PLA oder PETG, 0,2 mm Schicht, 3 Wände, 15 % Gyroid. Alle Teile passen einzeln auf die 256 × 256-Platte, der Körper ist das größte Teil.
- **Stützen**: global **aus**. Nur beim Körper: Stütztyp *Tree (manuell)* und mit dem Pinsel nur die runde Decke der Knopfmulde anmalen. Alles andere ist auf höchstens 45° oder als kurze Brücke konstruiert, auch das Lochfeld (Sechsecke mit flachem Dach, je 2,4 mm Brücke). Innen über den Lautsprecherflanschen gibt es zwei kurze Aussparungen (7 mm tief), die mit leichtem Durchhang ohne Stützen drucken; wer mag, malt dort auch Tree Supports an.
- **Schirm**: helles PLA, 0,2 mm Schicht, 3 Wände (= 1,2 mm), 0 % Füllung. Ohne Stützen, der Schirm ist oben und unten offen.
- **Lichtkern und Kerndeckel**: weißes PLA, wie Gehäuse.

## Schrauben und Kleinteile

| Schraube | Anzahl | Wofür | Werkzeug |
|---|---|---|---|
| BT3 × 12, Linsenkopf, selbstschneidend | 8 | Breitbänder und Passivmembran von innen in die Schallwände, vor dem Sockel durch die offene Unterseite | kurzer Kreuz PH1 oder Bit-Ratsche |
| BT3 × 10, Linsenkopf, selbstschneidend | 4 | Körper auf den Sockel (von unten aus dem Sockel) | Kreuz PH1 |
| BT3 × 10, Linsenkopf, selbstschneidend | 3 | Bodenplatte an den Sockel (unter den Gummifüßen) | Kreuz PH1 |
| BT2.6 × 6, Linsenkopf, selbstschneidend | 2 | LM2596 auf die Bodenplatte | Kreuz PH0 |
| Abstandsbolzen M2,5 × 11 (Innen/Außen) + M2,5 × 5 | 4 + 4 | Pi und DigiAMP+ (die Bolzen schneiden ihr Gewinde selbst in die Dome) | Steckschlüssel 5 mm |

Keine Senkkopfschrauben, keine Gewindeeinsätze. Alle selbstschneidenden Schrauben gibt es z. B. im Bambu Lab Maker's Supply.

Außerdem: 3 Gummifüße Ø 12 mm (decken die Bodenschrauben ab), Moosgummi-Dichtband 3 mm, etwas Silikon für die Kabeldurchführungen, ca. 30 g Polyesterwatte.

Elektronik und Lautsprecher: siehe [Hardware-Liste](../../docs/HARDWARE.md).

## Schirm befestigen

Die Spinne wird auf den Stift des Kerndeckels gesteckt, der Schirm liegt oben auf ihrem Ring. Keine Schrauben.

## Zusammenbauen

Schritt für Schritt mit Bildern: [Montageanleitung (PDF)](../../docs/pdf/Soundlampe_Montageanleitung.pdf). Maße und Konstruktionsregeln: [Konstruktionsplan](../../gehaeuse/KONSTRUKTIONSPLAN.md).
