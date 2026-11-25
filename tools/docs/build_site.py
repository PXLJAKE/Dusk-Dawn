#!/usr/bin/env python3
"""Baut die Doku-Website für den Unterpfad /docs/<slug>/ und packt sie optional als ZIP.

Ablauf:
1. `mkdocs build --strict` mit einer Platzhalter-Domain als site_url
   (https://docs.example.invalid/docs/<slug>/), Ausgabe nach <out>/docs/<slug>/.
2. Alle HTML-Seiten, die sitemap.xml und die Material-Konfiguration so umschreiben, dass jeder
   interne Link, jedes Asset und der Sprachumschalter mit /docs/<slug>/ beginnt und die
   Platzhalter-Domain nirgends mehr vorkommt. Die Domain der eigenen Website muss also nicht
   bekannt sein.
3. Mit --zip <version>: <out>/<slug>-docs-<version>.zip, darin genau ein Ordner <slug>/.

Aufruf aus dem Repo-Root:
    python tools/docs/build_site.py                  # nur bauen, Ergebnis in build/docs/dusk-dawn/
    python tools/docs/build_site.py --zip 0.4.0      # zusätzlich build/dusk-dawn-docs-0.4.0.zip
"""

from __future__ import annotations

import argparse
import gzip
import os
import posixpath
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PLACEHOLDER_ORIGIN = "https://docs.example.invalid"
SKIP_PREFIXES = ("#", "http:", "https:", "mailto:", "data:", "javascript:", "tel:", "//")

ATTR_RE = re.compile(r'(?P<attr>\b(?:href|src))=(?P<q>["\'])(?P<url>[^"\']*)(?P=q)')
SRCSET_RE = re.compile(r'\bsrcset=(?P<q>["\'])(?P<val>[^"\']*)(?P=q)')
# Material: __md_scope=new URL("..",location) und die JSON-Konfiguration im <script id="__config">
JS_URL_RE = re.compile(r'new URL\("(?P<url>[^"]*)",\s*location\)')
CONFIG_RE = re.compile(r'(<script id="__config" type="application/json">)(?P<json>.*?)(</script>)', re.DOTALL)
CONFIG_KEY_RE = re.compile(r'"(?P<key>base|search)":\s*"(?P<url>[^"]*)"')
# hreflang-Links im <head>: Material lädt für jeden davon <href>/sitemap.xml nach, das gibt es pro
# Seite nicht (404). Ohne Domain bringen sie für Suchmaschinen ohnehin nichts. Der sichtbare
# Sprachumschalter (<a hreflang>) bleibt erhalten.
HEAD_ALTERNATE_RE = re.compile(r'\s*<link rel="alternate" href="[^"]*" hreflang="[^"]*">')


def absolutize(url: str, page_dir: str, base_path: str) -> str:
    """Macht aus einem Link einen Pfad ab der Domain-Wurzel (z. B. /docs/dusk-dawn/faq/)."""
    if url.startswith(PLACEHOLDER_ORIGIN):
        return url[len(PLACEHOLDER_ORIGIN):] or "/"
    if not url or url.startswith(SKIP_PREFIXES) or url.startswith("/"):
        return url
    path, sep, frag = url.partition("#")
    path, qsep, query = path.partition("?")
    joined = posixpath.normpath(posixpath.join(page_dir, path)) if path else page_dir.rstrip("/")
    if path in ("", ".", "..") or path.endswith(("/", "/.", "/..")):
        joined = joined.rstrip("/") + "/"
    if not joined.startswith(base_path):
        raise ValueError(f"Link {url!r} auf {page_dir!r} zeigt aus {base_path} heraus")
    return joined + (qsep + query if qsep else "") + (sep + frag if sep else "")


def rewrite_html(text: str, page_dir: str, base_path: str) -> str:
    text = HEAD_ALTERNATE_RE.sub("", text)
    text = ATTR_RE.sub(
        lambda m: f'{m["attr"]}={m["q"]}{absolutize(m["url"], page_dir, base_path)}{m["q"]}', text
    )

    def fix_srcset(m: re.Match[str]) -> str:
        parts = []
        for item in m["val"].split(","):
            bits = item.strip().split(None, 1)
            if bits:
                bits[0] = absolutize(bits[0], page_dir, base_path)
            parts.append(" ".join(bits))
        return f'srcset={m["q"]}{", ".join(parts)}{m["q"]}'

    text = SRCSET_RE.sub(fix_srcset, text)
    text = JS_URL_RE.sub(lambda m: f'new URL("{absolutize(m["url"], page_dir, base_path)}",location)', text)
    text = CONFIG_RE.sub(
        lambda m: m.group(1)
        + CONFIG_KEY_RE.sub(
            lambda k: f'"{k["key"]}": "{absolutize(k["url"], page_dir, base_path)}"', m["json"]
        )
        + m.group(3),
        text,
    )
    return text.replace(PLACEHOLDER_ORIGIN, "")


def postprocess(site: Path, base_path: str) -> None:
    for html in sorted(site.rglob("*.html")):
        rel_dir = html.parent.relative_to(site).as_posix()
        page_dir = base_path if rel_dir == "." else f"{base_path}{rel_dir}/"
        html.write_text(rewrite_html(html.read_text(encoding="utf-8"), page_dir, base_path), encoding="utf-8")
    for xml in site.rglob("sitemap.xml"):
        xml.write_text(xml.read_text(encoding="utf-8").replace(PLACEHOLDER_ORIGIN, ""), encoding="utf-8")
        gz = xml.with_name("sitemap.xml.gz")
        if gz.exists():
            with gzip.GzipFile(gz, "wb", mtime=0) as fh:
                fh.write(xml.read_bytes())
    leftovers = [p for p in site.rglob("*") if p.is_file() and p.suffix in {".html", ".xml", ".json", ".js"}
                 and PLACEHOLDER_ORIGIN.encode() in p.read_bytes()]
    if leftovers:
        sys.exit(f"Platzhalter-Domain noch enthalten in: {', '.join(map(str, leftovers))}")


def make_zip(site: Path, slug: str, version: str, out: Path) -> Path:
    zip_path = out / f"{slug}-docs-{version}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(site.rglob("*")):
            arc = Path(slug) / path.relative_to(site)
            if path.is_dir():
                zf.writestr(arc.as_posix() + "/", "")
            else:
                zf.write(path, arc.as_posix())
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", default="dusk-dawn", help="Projektordner unter /docs/ (Standard: dusk-dawn)")
    parser.add_argument("--out", default="build", type=Path, help="Ausgabeordner (Standard: build)")
    parser.add_argument("--zip", metavar="VERSION", help="zusätzlich <slug>-docs-<VERSION>.zip erzeugen")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.slug):
        sys.exit("--slug darf nur a-z, 0-9 und - enthalten")
    if args.zip is not None and not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]*", args.zip):
        sys.exit("--zip: ungültige Version")

    base_path = f"/docs/{args.slug}/"
    site = args.out / "docs" / args.slug
    if site.exists():
        shutil.rmtree(site)
    env = dict(os.environ, DOCS_URL=PLACEHOLDER_ORIGIN + base_path, NO_MKDOCS_2_WARNING="1")
    if args.zip is not None:
        env["DOCS_VERSION"] = f"v{args.zip}"
    subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(site)], check=True, env=env)
    postprocess(site, base_path)
    print(f"Seite: {site}/  (gehört nach <docroot>{base_path})")
    if args.zip is not None:
        print(f"ZIP:   {make_zip(site, args.slug, args.zip, args.out)}")


if __name__ == "__main__":
    main()
