#!/usr/bin/env python3
"""Prüft die gebaute Seite unter dem Unterpfad /docs/<slug>/ mit einem echten HTTP-Server.

Liefert <out>/ per http.server aus (die Seite liegt in <out>/docs/<slug>/), liest jede HTML-Seite,
sammelt alle internen Links und Assets (href, src, srcset, Material-Konfiguration) und ruft jeden
einzeln ab. Fehler, wenn
  - ein interner Link nicht mit /docs/<slug>/ beginnt (z. B. relativ oder auf eine andere Wurzel),
  - ein Abruf nicht 200 liefert,
  - die Platzhalter-Domain irgendwo stehen geblieben ist.

Aufruf aus dem Repo-Root (nach build_site.py):
    python tools/docs/check_site.py
"""

from __future__ import annotations

import argparse
import functools
import html
import re
import sys
import threading
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

URL_RE = re.compile(r'\b(?:href|src)=["\']([^"\']*)["\']')
SRCSET_RE = re.compile(r'\bsrcset=["\']([^"\']*)["\']')
CONFIG_RE = re.compile(r'"(?:base|search)":\s*"([^"]*)"')
JS_URL_RE = re.compile(r'new URL\("([^"]*)",\s*location\)')
EXTERNAL = ("http:", "https:", "mailto:", "data:", "javascript:", "tel:", "//")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # kein Log pro Abruf
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default="dusk-dawn")
    parser.add_argument("--out", default="build", type=Path)
    args = parser.parse_args()

    base_path = f"/docs/{args.slug}/"
    site = args.out / "docs" / args.slug
    if not (site / "index.html").is_file():
        sys.exit(f"{site}/index.html fehlt, zuerst tools/docs/build_site.py ausführen")

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(args.out)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_address[1]}"

    errors: list[str] = []
    targets: dict[str, str] = {}
    pages = sorted(site.rglob("*.html"))
    for page in pages:
        text = page.read_text(encoding="utf-8")
        where = "/" + page.relative_to(args.out).as_posix()
        if "example.invalid" in text:
            errors.append(f"{where}: Platzhalter-Domain enthalten")
        urls = URL_RE.findall(text) + CONFIG_RE.findall(text) + JS_URL_RE.findall(text)
        for srcset in SRCSET_RE.findall(text):
            urls += [item.strip().split()[0] for item in srcset.split(",") if item.strip()]
        for raw in urls:
            url = html.unescape(raw)
            if not url or url.startswith("#") or url.startswith(EXTERNAL):
                continue
            if not url.startswith(base_path):
                errors.append(f"{where}: Link beginnt nicht mit {base_path}: {url}")
                continue
            targets.setdefault(url.split("#")[0], where)
    for extra in ("sitemap.xml", "search/search_index.json"):
        targets.setdefault(base_path + extra, "(fest)")
    sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
    for loc in re.findall(r"(?:<loc>|href=\")([^<\"]+)", sitemap):
        if not loc.startswith(base_path):
            errors.append(f"sitemap.xml: Eintrag beginnt nicht mit {base_path}: {loc}")
        targets.setdefault(loc, "sitemap.xml")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # lokal, nie über einen Proxy
    for url, where in sorted(targets.items()):
        try:
            with opener.open(origin + url, timeout=10) as resp:
                resp.read()
                if resp.status != 200:
                    errors.append(f"{url} -> {resp.status} (verlinkt in {where})")
        except urllib.error.HTTPError as err:
            errors.append(f"{url} -> {err.code} (verlinkt in {where})")
    server.shutdown()

    print(f"{len(pages)} Seiten, {len(targets)} verschiedene Links/Assets unter {base_path} abgerufen")
    if errors:
        print("\n".join(errors))
        sys.exit(f"{len(errors)} Fehler")
    print("Alle Links liefern 200.")


if __name__ == "__main__":
    main()
