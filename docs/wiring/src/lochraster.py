"""Erzeugt docs/wiring/lochraster.svg (Bestückungsplan der Lochraster-Platine)."""
P = 34; X0 = 330; Y0 = 150
def c(col, row): return X0 + col * P, Y0 + row * P
o = []
W, H = 1500, 760
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Inter, DejaVu Sans, sans-serif"><rect width="{W}" height="{H}" fill="#fff"/>')
o.append('<style>.v{stroke:#e8862a;stroke-width:7;fill:none;stroke-linecap:round;opacity:.9}.g{stroke:#222;stroke-width:7;fill:none;stroke-linecap:round;opacity:.85}.d{stroke:#2f6fd0;stroke-width:7;fill:none;stroke-linecap:round}.j{stroke:#2f6fd0;stroke-width:5;fill:none;stroke-dasharray:10 6}.l{font-size:15px;fill:#232a40}</style>')
o.append('<text x="40" y="50" font-size="30" font-weight="700" fill="#232a40">Lochraster-Platine · Bestückung</text>')
o.append('<text x="40" y="80" font-size="15" fill="#4a4a4a">Ansicht von oben (Bauteilseite), 30 × 70 mm, Raster 2,54 mm. Durchgezogene Linien = Lötbahnen unten (Drahtbrücken/Lötzinn), gestrichelt = isolierter Draht oben.</text>')
bx, by = c(-1, -1)
o.append(f'<rect x="{bx-6}" y="{by-6}" width="{29*P+12}" height="{12*P+12}" rx="8" fill="#e6efd9" stroke="#9fb38a" stroke-width="2"/>')
for col in range(-1, 28):
    for row in range(-1, 11):
        x, y = c(col, row)
        o.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#d2b06a" stroke="#b08a3a"/><circle cx="{x}" cy="{y}" r="1.8" fill="#fff"/>')
def line(pts, cls):
    o.append('<polyline points="' + ' '.join('%d,%d' % c(*p) for p in pts) + f'" class="{cls}"/>')
line([(0, 0), (26, 0)], 'v'); line([(0, 10), (26, 10)], 'g')
line([(0, 1), (0, 0)], 'v'); line([(0, 8), (0, 10)], 'g')
line([(6, 1), (6, 0)], 'v'); line([(6, 3), (6, 10)], 'g')
for col in (10, 11, 12, 14, 15): line([(col, 3), (col, 0)], 'v')      # 14,13,12,10,9 -> 5 V
for col in (10, 13, 14, 16): line([(col, 6), (col, 10)], 'g')          # 1,4,5,7 -> GND
line([(11, 7), (11, 6)], 'd'); line([(12, 6), (12, 8)], 'd'); line([(19, 8), (19, 5), (26, 5)], 'd')
line([(26, 4), (26, 0)], 'v'); line([(26, 6), (26, 10)], 'g')
x0, y0 = c(0, 5); x1, y1 = c(11, 7)
o.append(f'<path d="M{x0},{y0} C{x0+120},{y0-10} {x1-150},{y1+60} {x1},{y1}" class="j"/>')
xa, ya = c(12, 8); xb, yb = c(19, 8)
o.append(f'<line x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" stroke="#888" stroke-width="3"/>')
o.append(f'<rect x="{(xa+xb)/2-42}" y="{ya-11}" width="84" height="22" rx="10" fill="#d9b46c" stroke="#232a40" stroke-width="2"/>')
for i, colr in enumerate(['#f60', '#f60', '#8b4513', '#d4af37']):
    o.append(f'<rect x="{(xa+xb)/2-28+i*16}" y="{ya-11}" width="6" height="22" fill="{colr}"/>')
o.append(f'<rect x="{(xa+xb)/2-110}" y="{ya+14}" width="220" height="24" rx="5" fill="#fff" stroke="#d9b46c"/>')
o.append(f'<text x="{(xa+xb)/2}" y="{ya+31}" class="l" text-anchor="middle">330 Ω (orange-orange-braun)</text>')
x, y = c(10, 3); x2, y2 = c(16, 6)
o.append(f'<rect x="{x-14}" y="{y+12}" width="{x2-x+28}" height="{y2-y-24}" rx="4" fill="#232a40"/>')
o.append(f'<circle cx="{x}" cy="{(y+y2)/2}" r="8" fill="#3a4361"/>')
o.append(f'<text x="{(x+x2)/2}" y="{(y+y2)/2+6}" fill="#fff" font-size="17" font-weight="700" text-anchor="middle">74AHCT125</text>')
for i in range(7):
    xx, _ = c(10 + i, 6); o.append(f'<text x="{xx}" y="{y2-18}" font-size="12" fill="#fff" text-anchor="middle">{i+1}</text>')
    xx, _ = c(16 - i, 3); o.append(f'<text x="{xx}" y="{y+28}" font-size="12" fill="#fff" text-anchor="middle">{i+8}</text>')
ex, ey = c(6, 2)
o.append(f'<circle cx="{ex}" cy="{ey}" r="30" fill="#1b1b1b" opacity=".88"/><text x="{ex}" y="{ey-4}" fill="#fff" font-size="12" text-anchor="middle">1000 µF</text><text x="{ex}" y="{ey+12}" fill="#fff" font-size="12" text-anchor="middle">10 V</text><text x="{ex+38}" y="{ey-14}" class="l">+ Bein oben</text>')
for row, txt, col in [(1, '5 V vom LM2596 (OUT+)', '#b25f12'), (5, 'DATA vom Pi (Pin 19)', '#2f6fd0'), (8, 'GND vom Pi (Pin 39)', '#222'), (9, 'GND vom LM2596 (OUT–)', '#222')]:
    x, y = c(0, row)
    o.append(f'<rect x="{x-9}" y="{y-9}" width="18" height="18" fill="none" stroke="{col}" stroke-width="3"/>')
    o.append(f'<text x="{x-50}" y="{y+5}" class="l" text-anchor="end" fill="{col}">{txt}</text>')
for row, txt, col in [(4, '+5 V zum LED-Strip', '#b25f12'), (5, 'DIN zum LED-Strip', '#2f6fd0'), (6, 'GND zum LED-Strip', '#222')]:
    x, y = c(26, row)
    o.append(f'<rect x="{x-9}" y="{y-9}" width="18" height="18" fill="none" stroke="{col}" stroke-width="3"/>')
    o.append(f'<text x="{x+50}" y="{y+5}" class="l" fill="{col}">{txt}</text>')
notes = ['Pins: 1 (1OE) und 7 an GND · 14 (VCC) an 5 V · 2 (1A) = Daten rein · 3 (1Y) = Daten raus über 330 Ω',
         'Unbenutzte Kanäle festlegen: 4, 5 an GND · 9, 10, 12, 13 an 5 V · 6, 8, 11 bleiben frei',
         'Kerbe/Punkt des Chips zeigt nach links. Tipp: IC-Sockel einlöten, Chip erst zum Schluss einstecken.',
         'Kabel: Strom 0,5 mm² (rot/schwarz), Daten 0,14–0,25 mm². Platine mit Schaumklebeband links neben dem Pi befestigen.']
for i, t in enumerate(notes): o.append(f'<text x="40" y="{610+i*30}" font-size="17" fill="#333">{t}</text>')
o.append('</svg>')
open(__file__.rsplit('/', 2)[0] + '/lochraster.svg', 'w').write('\n'.join(o))
