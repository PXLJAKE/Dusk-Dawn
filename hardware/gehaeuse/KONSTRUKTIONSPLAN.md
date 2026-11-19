# Konstruktions- und Druckplan Gehäuse v2

Dieser Plan gilt für beide Fuß-Versionen (Kugel und Zylinder) und alle fünf Schirme. Er setzt die Erkenntnisse aus den ersten Prototypen um. Grundlage für alle Maße ist [`soundlampe.scad`](soundlampe.scad).

## 1. Fertigung (Bambu Lab P1S)

| Regel | Umsetzung |
|---|---|
| Bauraum 256 × 256 × 256 mm | Größtes Teil ist der Zylinder-Körper mit Ø 190 × 144 mm. Alle Teile passen einzeln auf die Platte. |
| Stützen nur gezielt | Wände höchstens 45° geneigt, Löcher in senkrechten Wänden als Tropfenform. **Tree Supports** (Baumstützen) nur an der Decke der Drehknopf-Mulde und am oberen Bogen der beiden runden Lautsprecher-Ausschnitte (Ø 100 mm, damit der Moosgummi-Ring dicht schließt). Alle anderen Teile drucken ohne Stützen: Schraubdome haben 45°-Kinne, der Knopfbecher ist unten spitz, Lichtkern und Kerndeckel werden so gedreht gedruckt, dass nur kurze Brücken bleiben. Die Ausrichtung steckt schon in den STL der Pakete. |
| Weniger Teile | Das Kabelrohr entfällt (Kabel läuft durch die Kammer, an Sockel und Kern mit Silikon abgedichtet), der Schirmsitz entfällt (der Deckel trägt den Schirm), Deckel, Sockel, Bodenplatte, Knopf und Lichtteile sind für beide Füße **dieselben Teile**. |
| Zugänglichkeit | Jede Schraube wird gerade angesetzt, bevor das nächste Teil sie verdeckt. Die Lautsprecher-Schrauben werden vor dem Sockel durch die offene Unterseite (Ø 112 mm) mit einem kurzen Kreuzschraubendreher oder einer Bit-Ratsche angezogen, alle anderen von unten. |

Teile pro Lampe (Kugel oder Zylinder mit Kugelschirm): Körper, Sockel, Bodenplatte, Deckel, Knopf, Stiel, Lichtkern, Kerndeckel, Schirm. Plissee und Glocke brauchen zusätzlich die Spinne.

## 2. Verbindungen und Schrauben

| Regel | Umsetzung |
|---|---|
| Keine Schraube von außen sichtbar | Lautsprecher-Schrauben sitzen innen in der Kammer, die Körper-Schrauben im Sockel, die Bodenplatten-Schrauben unter den Gummifüßen. Der Deckel hat keine Schrauben. |
| Keine Senkköpfe, selbstschneidende Kunststoffschrauben | Nur **BT3** (Ø 3 mm) und **BT2.6** mit Linsen- bzw. Flachkopf, z. B. aus dem Bambu Lab Maker's Supply. Vorbohrung im Modell: BT3 = 2,5 mm, BT2.6 = 2,1 mm, Schraubdom Ø 8 mm. |
| Gewindeeinsätze auf ein Minimum | **Keine** Einschmelzmuttern mehr. Alle Schraubstellen sind Dome für selbstschneidende Schrauben. |
| Lautsprecher ohne Einsätze | Die Außenwand bleibt rund, das Lochfeld ist direkt in die Wand gedruckt (Sechseck-Löcher mit flachem Dach, jedes Dach ist eine 2,4-mm-Brücke). Dahinter sitzt eine 7 mm starke **innere Schallwand**. Breitbänder und Passivmembran werden von innen mit Moosgummi daraufgelegt und mit 4 × BT3 × 10 je Chassis direkt in die Schallwand geschraubt (rund 6 mm Gewindelänge im Kunststoff, keine Einsätze). Die Vorbohrungen enden 6 mm tief, damit sie die Außenwand nicht durchstoßen (Lochkreis der Chassis: 110 mm auf den Diagonalen, gemessen). |
| Freigang für Kopf und Werkzeug | Um jedes Schraubenloch sind mindestens 5 mm radial frei (Ø 11 mm um den Kopf). Bodenplatten-Schrauben sitzen in 1 mm tiefen Mulden, die die Gummifüße abdecken. |
| Bajonett, Rast- und Steckverbindungen | **Deckel:** Bajonett mit 3 Nocken, eine Drittel-Drehung, kein Werkzeug. **Kabel:** ohne Rohr, Durchführungen mit Silikon abgedichtet. **Stiel, Lichtkern, Kerndeckel, Spinne:** gesteckt. |

### Schrauben pro Lampe (beide Füße gleich)

| Schraube | Anzahl | Wo |
|---|---|---|
| BT3 × 10, Linsenkopf | 8 | Breitbänder und Passivmembran von innen in die Schallwände |
| BT3 × 10, Linsenkopf | 4 | Körper auf den Sockel (von innen aus dem Sockel nach oben) |
| BT3 × 10, Linsenkopf | 3 | Bodenplatte an den Sockel (unter den Gummifüßen) |
| BT2.6 × 6, Linsenkopf | 2 | LM2596 auf die Bodenplatte |
| Abstandsbolzen M2,5 × 11 (Innen/Außen) + M2,5 × 5 | 4 + 4 | Pi und DigiAMP+ (Bolzen schneiden ihr Gewinde selbst in die Dome) |

## 3. Konstruktive Änderungen

### Eingelassener Drehknopf
- Rechts im Körper sitzt eine flache runde **Mulde** (Ø 33 mm, 5 mm tief), knapp größer als der Knopf (Ø 30 × 14 mm, gerändelt). Der Knopf steckt nur gut 4 mm darin und steht **10 mm** über die Außenkontur, so lässt er sich gut greifen, drehen und drücken. Drehgeber EC11 mit 15 mm Welle.
- Der Drehgeber wird von innen durch den Muldenboden gesteckt und mit seiner Mutter in der Mulde festgezogen. Der Knopf deckt die Mutter ab.
- Die Mulde ist ein geschlossener Becher, die Kammer bleibt dicht. Ihre Decke wird mit **Tree Supports** gedruckt.

### Deckel bündig, ohne Randschrauben
- Der Deckel liegt nicht mehr auf, er sitzt **in** der Kugel. Sein oberer Rand (4 mm) ist genau der fehlende Streifen der Kugel, darunter läuft ein 45°-Konus bis zum Bajonett. Die Kontur läuft ohne Kante durch, und der Deckel druckt mit der Oberseite nach oben ohne Stützen. Beim Zylinder schließt er bündig mit der flachen Oberseite ab.
- Befestigt wird er mit einem **Bajonett** (3 Nocken, die unter einen Kragen am unteren Ende des Konus greifen). Es gibt keine Schraubenlöcher mehr in der gekrümmten Kugelwand.
- Ein Moosgummi-Ring auf dem Konus dichtet die Kammer und hält das Bajonett unter Spannung.

### Schirme und Schirmaufnahme
- Alle Schirme sind **oben und unten offen**, als Hülle mit 1,2 mm Wand.
- **Ein Deckel für alle:** Der Deckel hat oben eine 1,6 mm tiefe Ringmulde. Kolben, Twist und Laterne stehen mit ihrem Fußring darin und werden vom Stiel und Kerndeckel gehalten. Plissee und Glocke hängen wie bisher mit der Spinne am Kerndeckel.
- **Nahtloser Übergang:** Kolben, Twist und Laterne beginnen unten mit genau dem Außendurchmesser der Kugel an dieser Stelle (Ø 147 mm). Sie laufen dort unter derselben Neigung (45°) weiter wie die Kugel und gehen erst dann in ihre eigene Form über. Die Rippen laufen nach unten auf null aus, deshalb gibt es keinen Absatz.
- Alle Profile sind als glatte Kurven (Hermite-Splines) definiert, die Steigung bleibt überall unter 45°. So drucken sie ohne Stützen, auch im Vasenmodus.

### Weitere Vereinheitlichung
- Kugel und Zylinder sind gleich hoch (188 mm). Damit sind auch die **Stiellängen** gleich: 140 mm für Plissee und Glocke, 95 mm für Kolben, Twist und Laterne.
- Beide Körper stehen auf demselben schlanken **Sockel** (Ø 150 × 44 mm) mit Schattenfuge. Die Sockeldecke ist der Boden der Lautsprecherkammer.
- Deckel, Knopf, Sockel und Bodenplatte sind identisch.

## 4. Ergebnis

- Modell: [`soundlampe.scad`](soundlampe.scad) (`base = "kugel"` oder `"zylinder"`, `shade_style = ...`).
- Explosionszeichnungen: [`renders/`](renders/).
- Fertige Druckpakete je Kombination: [`../pakete/`](../pakete/).
- Version 1 liegt unverändert in [`archiv/`](archiv/).
