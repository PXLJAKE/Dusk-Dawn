#!/usr/bin/env python3
"""Baut je Druckpaket eine ZIP-Datei mit allen STL, Anleitung und PDFs.

Aufruf:  python3 hardware/gehaeuse/werkzeug/zip_bauen.py [ausgabeordner]
Standard-Ausgabe: dist/druckpakete/<variante>.zip (nur Standardbibliothek).

Inhalt jeder ZIP:
  LIES_MICH_ZUERST.html   Anleitung dieser Variante (aus pakete/<variante>/README.md)
  Hardware-Liste.html     Einkaufsliste und Verdrahtung (aus docs/HARDWARE.md)
  Montageanleitung.pdf    Zusammenbau Schritt für Schritt
  Bauanleitung.pdf        Gesamtübersicht
  vorschau.png            Bild der Variante
  stl/                    alle Druckteile (schon auf der Platte ausgerichtet)
"""
import html
import re
import sys
import zipfile
from pathlib import Path

HW = Path(__file__).resolve().parents[2]
PAKETE = HW / "pakete"
DOCS = HW / "docs"

CSS = """
body{font:16px/1.55 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;color:#222}
table{border-collapse:collapse;margin:1rem 0;width:100%}
th,td{border:1px solid #ccc;padding:.35rem .6rem;text-align:left;vertical-align:top}
th{background:#f0f0f0} code{background:#f3f3f3;padding:0 .25rem;border-radius:3px}
img{max-width:100%} h1,h2,h3{line-height:1.25}
.kasten{background:#fff6dd;border:1px solid #e0c060;padding:.8rem 1rem;border-radius:6px}
"""

LINKS = {  # relative Links im README -> Dateien in der ZIP
    "../../docs/pdf/Soundlampe_Montageanleitung.pdf": "Montageanleitung.pdf",
    "../../docs/pdf/Soundlampe_Bauanleitung.pdf": "Bauanleitung.pdf",
    "../../docs/HARDWARE.md": "Hardware-Liste.html",
}


def inline(t, links):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', t)

    def link(m):
        text, url = m.group(1), m.group(2)
        url = links.get(url.split("#")[0], None) if url.startswith("..") else url
        if url is None:  # Verweis auf Repo-Datei, die nicht in der ZIP liegt
            return text
        return f'<a href="{url}">{text}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)


def md_to_html(md, title, links):
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            n = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{n}>{inline(ln[n:].strip(), links)}</h{n}>")
        elif ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            head = [c.strip() for c in ln.strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            i -= 1
            out.append("<table><tr>" + "".join(f"<th>{inline(c, links)}</th>" for c in head) + "</tr>")
            for r in rows:
                out.append("<tr>" + "".join(f"<td>{inline(c, links)}</td>" for c in r) + "</tr>")
            out.append("</table>")
        elif re.match(r"^\s*([-*]|\d+\.)\s", ln):
            tag = "ol" if re.match(r"^\s*\d+\.", ln) else "ul"
            out.append(f"<{tag}>")
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s", lines[i]):
                out.append("<li>" + inline(re.sub(r"^\s*([-*]|\d+\.)\s", "", lines[i]), links) + "</li>")
                i += 1
            i -= 1
            out.append(f"</{tag}>")
        elif ln.startswith(">"):
            out.append(f'<p class="kasten">{inline(ln.lstrip("> "), links)}</p>')
        elif ln.strip():
            out.append(f"<p>{inline(ln, links)}</p>")
        i += 1
    return (f'<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f"<style>{CSS}</style><body>" + "\n".join(out) + "</body></html>")


def build(variant_dir, out_dir):
    name = variant_dir.name
    readme = (variant_dir / "README.md").read_text(encoding="utf-8")
    title = readme.splitlines()[0].lstrip("# ").strip()
    intro = ("> **So gehst du vor:** 1. Diese ZIP entpacken. 2. Alle Dateien im Ordner `stl/` in Bambu Studio "
             "laden und mit den Einstellungen unten drucken. 3. Schrauben und Kleinteile aus der Liste besorgen. "
             "4. Mit der `Montageanleitung.pdf` zusammenbauen. Einkaufsliste: `Hardware-Liste.html`.\n\n")
    first, _, rest = readme.partition("\n")
    page = md_to_html(first + "\n\n" + intro + rest, title, {**LINKS})
    hw_page = md_to_html((DOCS / "HARDWARE.md").read_text(encoding="utf-8"), "Hardware-Liste", {})
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(f"{name}/LIES_MICH_ZUERST.html", page)
        z.writestr(f"{name}/Hardware-Liste.html", hw_page)
        z.write(DOCS / "pdf/Soundlampe_Montageanleitung.pdf", f"{name}/Montageanleitung.pdf")
        z.write(DOCS / "pdf/Soundlampe_Bauanleitung.pdf", f"{name}/Bauanleitung.pdf")
        z.write(variant_dir / "vorschau.png", f"{name}/vorschau.png")
        for stl in sorted(variant_dir.glob("*.stl")):
            z.write(stl, f"{name}/stl/{stl.name}")
    return target


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HW.parent / "dist" / "druckpakete"
    for v in sorted(p for p in PAKETE.iterdir() if p.is_dir()):
        t = build(v, out_dir)
        print(f"{t.name}: {t.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
