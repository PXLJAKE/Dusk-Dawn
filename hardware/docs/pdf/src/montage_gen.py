"""Erzeugt ../montage.html (Montageanleitung Gehäuse v2).

PDF danach mit einem Headless-Browser drucken (A4, Hintergrundgrafik an).
Bilder: img/montage/s1.png ... s9b.png, gerendert mit part="step" in hardware/gehaeuse/soundlampe.scad.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KOPF = open(os.path.join(HERE, "montage_kopf.html"), encoding="utf-8").read()


def bt(d, length, head_d, head_h=None):
    """Selbstschneidende Linsenkopfschraube, seitlich, 1:1 in mm."""
    head_h = head_h or round(head_d * 0.42, 2)
    w = head_h + length
    lines = "".join(
        f'<line x1="{head_h + 0.5 + i * 0.9:.2f}" y1="{(head_d - d) / 2:.2f}" x2="{head_h + 0.9 + i * 0.9:.2f}" '
        f'y2="{(head_d + d) / 2:.2f}" stroke="#7a8087" stroke-width=".14"/>'
        for i in range(int((length - 1.6) / 0.9)))
    y0, y1, ym = (head_d - d) / 2, (head_d + d) / 2, head_d / 2
    return (f'<svg class="scr" width="{w:.1f}mm" height="{head_d}mm" viewBox="0 0 {w:.2f} {head_d}">'
            f'<path d="M{head_h},0 C0,0 0,0 0,{ym} C0,{head_d} 0,{head_d} {head_h},{head_d} Z" fill="#8d939b"/>'
            f'<path d="M{head_h},{y0} L{w - 1.4},{y0} L{w},{ym} L{w - 1.4},{y1} L{head_h},{y1} Z" fill="#a9aeb5"/>{lines}</svg>')


def standoff():
    return ('<svg class="scr" width="17mm" height="5mm" viewBox="0 0 17 5"><polygon points="0,0.4 11,0.4 11,4.6 0,4.6" '
            'fill="#c9a14a"/><rect x="11" y="1.25" width="6" height="2.5" fill="#d8b766"/></svg>')


BT3_12 = bt(3, 12, 5.6)
BT3_10 = bt(3, 10, 5.6)
BT26_6 = bt(2.6, 6, 4.8)
M25_5 = bt(2.5, 5, 4.5)


def chip(n, svg, label):
    return f'<span class="chip"><b>{n}×</b>{svg}<span>{label}</span></span>'


def step(num, img, title, parts, chips, body, cyl=None, pic_h=None):
    ph = f' style="height:{pic_h}mm"' if pic_h else ""
    ih = f' style="max-height:{pic_h - 4}mm"' if pic_h else ""
    c = f'<div class="cyl"><b>Zylinder:</b> {cyl}</div>' if cyl else ""
    return (f'<div class="step"><div class="pic"{ph}><span class="num">{num}</span><img src="img/montage/{img}.png"{ih}></div><div>'
            f'<h3>{title}</h3><div class="need"><div class="t">Du brauchst</div><div class="parts">{parts}</div>{"".join(chips)}</div>'
            f'{body}{c}</div></div>')


def page(eyebrow, h2, content, nr):
    return (f'<section class="page"><div class="eyebrow">{eyebrow}</div><h2>{h2}</h2>{content}'
            f'<div class="foot"><span>Soundlampe · Montageanleitung v2</span><span>{nr}</span></div></section>')


def code(*names):
    return ", ".join(f"<code>{n}</code>" for n in names)


cover = f'''<section class="page cover"><div class="top"><div class="eyebrow">Montageanleitung · Gehäuse v2 · November 2026</div>
<h1>Soundlampe<br>zusammenbauen</h1><p class="sub">Schritt für Schritt mit Bildern, wie bei Lego. Bei jedem Schritt steht, welche Teile und
welche Schrauben du brauchst. Die Schrauben sind in Originalgröße gezeichnet: PDF in 100 % drucken und die Schraube aufs Papier legen.</p>
<div class="toc"><div><b>2</b>Was du brauchst</div><div><b>3</b>Lautsprecher, Drehknopf</div><div><b>4</b>Sockel, Elektronik</div>
<div><b>5</b>Bodenplatte, Deckel</div><div><b>6</b>Lichtkern</div><div><b>7</b>Schirm</div></div></div>
<div class="imgs"><img src="img/montage/cover_zylinder.png" style="height:120mm;margin-right:-6mm"><img src="img/montage/cover_kugel.png" style="height:165mm"></div></section>'''

need = f'''<p class="lead">Kugel und Zylinder werden genau gleich gebaut. Bis auf den Körper und die Schirmteile sind alle Druckteile dieselben.
Welche Dateien du druckst, steht im Paketordner deiner Variante (<code>hardware/pakete/&lt;fuss&gt;-&lt;schirm&gt;/</code>).</p>
<h3>Schrauben</h3><p class="scale">Nur Linsenkopf, selbstschneidend für Kunststoff (BT = „Blechtreib“-Gewinde, z. B. Bambu Lab Maker's Supply).
Keine Senkköpfe, keine Gewindeeinsätze, kein Lötkolben fürs Gehäuse.</p>
<table><tr><th></th><th>Schraube</th><th>Anzahl</th><th>Schritt</th><th>Wofür</th></tr>
<tr><td>{BT3_12}</td><td><b>BT3 × 12</b></td><td>8</td><td>1</td><td>Breitbänder und Passivmembran von innen in die Schallwände</td></tr>
<tr><td>{BT3_10}</td><td><b>BT3 × 10</b></td><td>4</td><td>3</td><td>Körper auf den Sockel, von unten</td></tr>
<tr><td>{BT3_10}</td><td><b>BT3 × 10</b></td><td>3</td><td>5</td><td>Bodenplatte an den Sockel, unter den Gummifüßen</td></tr>
<tr><td>{BT26_6}</td><td><b>BT2.6 × 6</b></td><td>2</td><td>4</td><td>LM2596 auf die Bodenplatte</td></tr>
<tr><td>{standoff()}</td><td><b>Abstandsbolzen M2,5 × 11</b></td><td>4</td><td>4</td><td>Pi auf die Bodenplatte, schneiden ihr Gewinde selbst</td></tr>
<tr><td>{M25_5}</td><td><b>M2,5 × 5</b></td><td>4</td><td>4</td><td>DigiAMP+ auf die Bolzen</td></tr></table>
<h3>Stiel: Länge hängt nur vom Schirm ab</h3>
<table><tr><th>Schirm</th><th>Stiel</th><th>Datei im Paket</th></tr>
<tr><td><b>Plissee, Glocke</b></td><td>140 mm</td><td><code>06_stiel_140mm.stl</code></td></tr>
<tr><td><b>Kolben, Twist, Laterne</b></td><td>95 mm</td><td><code>06_stiel_95mm.stl</code></td></tr></table>
<p>Statt gedruckt geht auch Messingrohr: Ø 20 mm außen, mindestens 13 mm innen, gleiche Länge. 18 mm davon stecken im Deckel.</p>
<h3>Sonst noch</h3>
<table><tr><td><b>Werkzeug</b></td><td>Kreuzschraubendreher PH1 (dazu ein kurzer PH1-Stummel oder eine Bit-Ratsche für die Lautsprecher) und PH0, Steckschlüssel 5 mm, Lötkolben für Kabel, Multimeter</td></tr>
<tr><td><b>Dichten</b></td><td>Moosgummi-Dichtband 3 mm (Lautsprecherflansche, Deckel), Silikon (Kabeldurchführungen)</td></tr>
<tr><td><b>Dämmen</b></td><td>Polyesterwatte ca. 30 g</td></tr>
<tr><td><b>Füße</b></td><td>3 Gummifüße Ø 12 mm, selbstklebend (sie decken die Bodenschrauben ab)</td></tr></table>'''

p3 = (step(1, "s1", "Lautsprecher von innen anschrauben", "Körper, Breitbänder ND105-4, Passivmembran ND105-PR, Moosgummi",
           [chip(8, BT3_12, "BT3 × 12")],
           "<p>Moosgummi auf die Flansche kleben, an den Breitbänder 2 Kabel (ca. 30 cm) löten, rot = +. Den <b>Breitbänder vorne</b> "
           "(Lochfeld links vom Knopf), die <b>Passivmembran hinten</b> durch die große Öffnung oben oder unten in den Körper führen und von innen "
           "gegen die innere Schallwand legen. Je 4 Schrauben über Kreuz direkt in den Kunststoff drehen.</p>"
           "<div class=\"note\">Das geht mit einem kurzen Kreuzschraubendreher (PH1, Stummel) oder einer kleinen Bit-Ratsche durch die offene "
           "Unterseite. Darum kommt der Sockel erst danach.</div>",
           "genauso, die inneren Schallwände sitzen vorne und hinten hinter dem Lochfeld.", 92) +
      step(2, "s2", "Drehgeber und Knopf", f"Drehgeber EC11 mit Mutter, {code('05_knopf')}", [],
           "<p>Drehgeber <b>von innen</b> (durch die offene Unterseite) durch das Loch im Boden der Knopfmulde stecken, die kleine Nase in "
           "ihr Loch. Mutter in der Mulde anziehen, Gewinde mit etwas Silikon dichten. 5 Litzen anlöten und nach unten führen. "
           "Knopf auf die D-Welle stecken: er steckt ein paar Millimeter in der flachen Mulde und steht etwa 10 mm heraus.</p>",
           "gleich, die Mulde sitzt rechts in der Wand.", 92))

p4 = (step(3, "s3", "Körper auf den Sockel", f"{code('02_sockel')}, Polyesterwatte, Silikon", [chip(4, BT3_10, "BT3 × 10")],
           "<p>Polyesterwatte locker in die Kammer legen, Lautsprecher frei lassen. Lautsprecher- und Drehgeberkabel durch die "
           "Löcher in der Sockeldecke nach unten fädeln. Körper aufsetzen (Knopf rechts) und "
           "<b>von unten aus dem Sockel</b> mit 4 Schrauben anziehen. Die Kabellöcher mit Silikon schließen, die Kammer muss dicht sein.</p>",
           None, 92) +
      step(4, "s4", "Elektronik auf die Bodenplatte", f"{code('03_bodenplatte')}, Pi 3 A+, DigiAMP+, LM2596, DC-Buchse",
           [chip(4, standoff(), "Abstandsbolzen M2,5 × 11"), chip(4, M25_5, "M2,5 × 5"), chip(2, BT26_6, "BT2.6 × 6")],
           '<ol class="steps"><li><b>LM2596 zuerst einstellen:</b> allein an 19 V, Poti drehen bis 5,1 V am Ausgang.</li>'
           "<li>Pi auf die 4 kurzen Dome legen, die Abstandsbolzen durch den Pi in die Dome drehen.</li>"
           "<li>DigiAMP+ aufstecken, mit 4 × M2,5 × 5 auf die Bolzen schrauben.</li>"
           "<li>LM2596 mit 2 Schrauben diagonal auf die Dome vorne.</li>"
           "<li>DC-Buchse hinten in den Sockel, alles nach dem Stromlaufplan (Bauanleitung) verkabeln.</li></ol>", None, 92))

p5 = (      step(5, "s5", "Bodenplatte anschrauben", "3 Gummifüße", [chip(3, BT3_10, "BT3 × 10")],
           "<p>Erst testen: Netzteil einstecken, die Lampe erscheint nach etwa einer Minute in Home Assistant. Dann die Platte "
           "einsetzen und von unten mit 3 Schrauben anziehen. Die Köpfe liegen in kleinen Mulden, die Gummifüße kommen direkt "
           "darauf und verdecken sie.</p>", None, 92) +
      step(6, "s6", "Deckel einsetzen (Bajonett)", f"{code('04_deckel')}, Moosgummi-Ring, Draht als Zugband", [],
           "<p>Zugband von oben durch den Kanal im Deckel und die Kammer bis nach unten schieben, das LED-Kabel (3 Adern) "
           "daran nach oben ziehen. Moosgummi-Ring auf den Sitz legen. Deckel so einsetzen, dass die 3 Nocken in die 3 Schlitze "
           "fallen, und mit den zwei Fingerlöchern <b>eine Drittel-Drehung im Uhrzeigersinn</b> drehen. Keine Schrauben: der Rand "
           "liegt danach bündig in der Kontur.</p>", "der Deckel ist derselbe, er sitzt bündig in der flachen Oberseite.", 92))

p6 = (step(7, "s7", "Stiel, Lichtkern, Kerndeckel",
           f"{code('06_stiel_…', '07_lichtkern', '08_kerndeckel')}, LED-Strip 0,5 m", [],
           "<p>LED-Kabel durch den Stiel ziehen, Stiel in die Buchse im Deckel stecken. Strip in 4 Windungen um den Kern kleben, "
           "Anschluss unten: rot +5V, schwarz GND, blau DIN. Kern mit seinem Zapfen in den Stiel, Kerndeckel aufsetzen: der "
           "Ring auf dem Kern greift in die Nut des Deckels.</p>", None, 120))

p7 = ('<div class="two"><div>' +
      step("8a", "s8a", "Plissee und Glocke", f"{code('09_spinne', '10_schirm_…')}", [],
           "<p>Spinne auf den langen Stift des Kerndeckels stecken. Schirm von oben darüberstülpen, er liegt auf dem Ring der "
           "Spinne. Keine Schrauben.</p>", None, 110).replace('class="step"', 'class="step" style="display:block;border:none"') +
      '</div><div>' +
      step("8b", "s8b", "Kolben, Twist und Laterne", f"{code('10_schirm_…')}", [],
           "<p>Schirm über den Lichtkern stülpen und mit seinem Fußring in die Ringmulde oben im Deckel stellen. Er läuft "
           "ohne Absatz aus der Kugel heraus. Kein Adapter, keine Schrauben. Wer ihn sichern will, legt ein Stück "
           "Silikon-Klebeband in die Mulde.</p>", None, 110).replace('class="step"', 'class="step" style="display:block;border:none"') +
      '</div></div><div class="note"><b>Fertig.</b> Schirm wechseln geht jederzeit: Schirm abheben, Kerndeckel und Stiel tauschen '
      '(140 mm für Plissee und Glocke, 95 mm für die Kugelschirme), neuen Schirm drauf.</div>')

html = (KOPF.replace("<title>Soundlampe Montageanleitung</title>", "<title>Soundlampe Montageanleitung v2</title>") + cover +
        page("Vorbereitung", "Was du brauchst", need, 2) +
        page("Schritt 1–2", "Lautsprecher und Drehknopf", p3, 3) +
        page("Schritt 3–4", "Sockel und Elektronik", p4, 4) +
        page("Schritt 5–6", "Bodenplatte und Deckel", p5, 5) +
        page("Schritt 7", "Lichtkern", p6, 6) +
        page("Schritt 8", "Schirm", p7, 7) + "</body></html>\n")
open(os.path.join(HERE, "..", "montage.html"), "w", encoding="utf-8").write(html)
print("montage.html geschrieben")
