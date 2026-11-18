"""Baut die zehn Druckpakete in hardware/pakete/ aus fertigen Binär-STLs.

Aufruf:  python3 pakete_bauen.py <ordner mit binär-STLs> [<ordner mit vorschaubildern>]
Die Vorschaubilder heißen <fuss>-<schirm>.png (z. B. kugel-laterne.png).
"""
import os, shutil, sys

SRC = sys.argv[1]
PREV = sys.argv[2] if len(sys.argv) > 2 else None
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "pakete"))

FUESSE = {"kugel": "Kugel", "zylinder": "Zylinder"}
SCHIRME = {
    "plissee": ("Plissee", 140, False, "gefaltet, hängt an der Spinne"),
    "glocke": ("Glocke", 140, False, "geschwungen, hängt an der Spinne"),
    "kolben": ("Kolben", 95, True, "bauchig, steht im Deckel und läuft bündig aus der Kugel"),
    "twist": ("Twist", 95, True, "gedrehte Rippen, steht im Deckel"),
    "laterne": ("Laterne", 95, True, "drei Wellen, steht im Deckel"),
}

# (nr, datei-quelle, zielname, anzahl, bezeichnung, farbe, stützen, hinweis)
def teile(fuss, schirm):
    name, stiel, auf_deckel, _ = SCHIRME[schirm]
    t = [
        ("body_" + fuss, f"01_koerper_{fuss}.stl", 1, f"Körper ({FUESSE[fuss]})", "Gehäusefarbe",
         "**Tree Supports (manuell)**: nur die Decke der Knopfmulde anmalen", "liegt richtig herum, Flansch auf der Platte"),
        ("plinth", "02_sockel.stl", 1, "Sockel", "Gehäusefarbe", "keine", "steht kopfüber (Decke auf der Platte)"),
        ("plate", "03_bodenplatte.stl", 1, "Bodenplatte", "Gehäusefarbe", "keine", ""),
        ("lid", "04_deckel.stl", 1, "Deckel (Bajonett)", "Gehäusefarbe", "keine", "Oberseite nach oben"),
        ("knob", "05_knopf.stl", 1, "Drehknopf", "Akzentfarbe", "keine", "Rückseite auf der Platte"),
        ("stem_" + schirm, f"06_stiel_{stiel}mm.stl", 1, f"Stiel {stiel} mm", "Akzent oder Messing",
         "keine", "oder Messingrohr Ø 20 mm außen, ≥ 13 mm innen, " + f"{stiel} mm lang"),
        ("led_core", "07_lichtkern.stl", 1, "Lichtkern", "Weiß", "keine", "kopfüber, die kleine Brücke im Boden druckt frei"),
        ("core_cap_" + schirm, "08_kerndeckel.stl", 1, "Kerndeckel", "Weiß", "keine", "flach auf der Platte, Stift nach oben"),
    ]
    if not auf_deckel:
        t.append(("spider_" + schirm, "09_spinne.stl", 1, "Spinne (Schirmhalter)", "Schirmfarbe", "keine", ""))
    t.append(("shade_" + schirm, f"10_schirm_{schirm}.stl", 1, f"Schirm {name}", "Weiß/Natur, lichtdurchlässig",
              "keine", "3 Wände, 0 % Füllung, keine obere/untere Deckschicht nötig (Schirm ist offen)"))
    return t

SCHRAUBEN = """| Schraube | Anzahl | Wofür | Werkzeug |
|---|---|---|---|
| BT3 × 12, Linsenkopf, selbstschneidend | 8 | Breitbänder und Passivmembran von innen in die Schallwände, vor dem Sockel durch die offene Unterseite | kurzer Kreuz PH1 oder Bit-Ratsche |
| BT3 × 10, Linsenkopf, selbstschneidend | 4 | Körper auf den Sockel (von unten aus dem Sockel) | Kreuz PH1 |
| BT3 × 10, Linsenkopf, selbstschneidend | 3 | Bodenplatte an den Sockel (unter den Gummifüßen) | Kreuz PH1 |
| BT2.6 × 6, Linsenkopf, selbstschneidend | 2 | LM2596 auf die Bodenplatte | Kreuz PH0 |
| Abstandsbolzen M2,5 × 11 (Innen/Außen) + M2,5 × 5 | 4 + 4 | Pi und DigiAMP+ (die Bolzen schneiden ihr Gewinde selbst in die Dome) | Steckschlüssel 5 mm |

Keine Senkkopfschrauben, keine Gewindeeinsätze. Alle selbstschneidenden Schrauben gibt es z. B. im Bambu Lab Maker's Supply."""

def readme(fuss, schirm):
    name, stiel, auf_deckel, beschr = SCHIRME[schirm]
    rows = "\n".join(f"| `{ziel}` | {n} | {bez} | {farbe} | {st} | {hin} |"
                     for _, ziel, n, bez, farbe, st, hin in teile(fuss, schirm))
    halter = ("Der Schirm steht mit seinem Fußring in der Ringmulde oben im Deckel und läuft bündig aus der Körperkontur heraus. "
              "Kein Adapterring, keine Schrauben. Wer ihn gegen Verrutschen sichern will, legt ein Stück Silikon-Klebeband in die Mulde."
              if auf_deckel else
              "Die Spinne wird auf den Stift des Kerndeckels gesteckt, der Schirm liegt oben auf ihrem Ring. Keine Schrauben.")
    return f"""# Paket: {FUESSE[fuss]} mit Schirm {name}

![Vorschau](vorschau.png)

Alles, was du für diese Variante druckst, liegt in diesem Ordner. Die STL-Dateien sind schon richtig auf der Druckplatte ausgerichtet, einfach in Bambu Studio laden.

Schirm: **{name}**, {beschr}. Stiel: **{stiel} mm**.

## Druckteile

| Datei | Anzahl | Teil | Filament | Stützen | Hinweis |
|---|---|---|---|---|---|
{rows}

### Einstellungen (Bambu Lab P1S, 0,4-mm-Düse)

- **Gehäuseteile** (Körper, Sockel, Platte, Deckel, Knopf): PLA oder PETG, 0,2 mm Schicht, 3 Wände, 15 % Gyroid. Alle Teile passen einzeln auf die 256 × 256-Platte, der Körper ist das größte Teil.
- **Stützen**: global **aus**. Nur beim Körper: Stütztyp *Tree (manuell)* und mit dem Pinsel nur die runde Decke der Knopfmulde anmalen. Alles andere ist auf höchstens 45° oder als kurze Brücke konstruiert, auch das Lochfeld (Sechsecke mit flachem Dach, je 2,4 mm Brücke). Innen über den Lautsprecherflanschen gibt es zwei kurze Aussparungen (7 mm tief), die mit leichtem Durchhang ohne Stützen drucken; wer mag, malt dort auch Tree Supports an.
- **Schirm**: helles PLA, 0,2 mm Schicht, 3 Wände (= 1,2 mm), 0 % Füllung. Ohne Stützen, der Schirm ist oben und unten offen.
- **Lichtkern und Kerndeckel**: weißes PLA, wie Gehäuse.

## Schrauben und Kleinteile

{SCHRAUBEN}

Außerdem: 3 Gummifüße Ø 12 mm (decken die Bodenschrauben ab), Moosgummi-Dichtband 3 mm, etwas Silikon für die Kabeldurchführungen, ca. 30 g Polyesterwatte.

Elektronik und Lautsprecher: siehe [Hardware-Liste](../../docs/HARDWARE.md).

## Schirm befestigen

{halter}

## Zusammenbauen

Schritt für Schritt mit Bildern: [Montageanleitung (PDF)](../../docs/pdf/Soundlampe_Montageanleitung.pdf). Maße und Konstruktionsregeln: [Konstruktionsplan](../../gehaeuse/KONSTRUKTIONSPLAN.md).
"""

for fuss in FUESSE:
    for schirm in SCHIRME:
        d = os.path.join(ROOT, f"{fuss}-{schirm}")
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
        for src, ziel, *_ in teile(fuss, schirm):
            shutil.copyfile(os.path.join(SRC, src + ".stl"), os.path.join(d, ziel))
        with open(os.path.join(d, "README.md"), "w") as f:
            f.write(readme(fuss, schirm))
        if PREV:
            shutil.copyfile(os.path.join(PREV, f"{fuss}-{schirm}.png"), os.path.join(d, "vorschau.png"))
        print("ok", d)
