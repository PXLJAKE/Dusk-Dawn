# Doku-Website: bauen und als ZIP bereitstellen

Die Doku-Website entsteht mit MkDocs (Material-Theme) aus `website/de/` und `website/en/`, Einstellungen in [`mkdocs.yml`](../../mkdocs.yml). Sie gehört auf deiner Website in den Ordner `docs/dusk-dawn/` und ist dann unter `/docs/dusk-dawn/` erreichbar. Die Domain muss dafür nicht bekannt sein.

## Fertige Seite übernehmen

1. Am GitHub-Release die Datei `dusk-dawn-docs-<version>.zip` herunterladen.
2. Entpacken. Darin liegt genau ein Ordner `dusk-dawn/`.
3. Diesen Ordner in den `docs`-Ordner deiner Website kopieren (vorher den alten `dusk-dawn/` löschen, damit keine veralteten Seiten liegen bleiben). Ergebnis: `<docroot>/docs/dusk-dawn/index.html`.

Alle Links, Bilder, Skripte, die Suche und der Sprachumschalter verwenden Pfade ab `/docs/dusk-dawn/`. Die Seite funktioniert deshalb nur genau unter diesem Pfad.

## Lokal bauen

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r tools/docs/requirements.txt
mkdocs serve                                   # Vorschau auf http://127.0.0.1:8000/ (relative Links)
python tools/docs/build_site.py --zip 0.4.0    # build/docs/dusk-dawn/ und build/dusk-dawn-docs-0.4.0.zip
python tools/docs/check_site.py                # liefert build/ per HTTP aus und ruft jeden Link ab
```

`build_site.py` baut mit der Platzhalter-Domain `https://docs.example.invalid/docs/dusk-dawn/` als `site_url` und entfernt die Domain danach aus HTML und `sitemap.xml`. Relative Links schreibt es auf Pfade ab `/docs/dusk-dawn/` um. Die `hreflang`-Links im `<head>` fallen weg: Ohne Domain nützen sie Suchmaschinen nichts, und Material würde für jeden davon eine nicht vorhandene `sitemap.xml` abfragen. Der sichtbare Sprachumschalter bleibt.

`check_site.py` bricht ab, wenn ein interner Link nicht mit `/docs/dusk-dawn/` beginnt, ein Abruf nicht 200 liefert oder die Platzhalter-Domain noch irgendwo steht.

Markdown-Lint: `npm ci --prefix tools/docs && tools/docs/node_modules/.bin/markdownlint-cli2`

## Versionen aktualisieren

- Python: Versionen in `requirements.in` ändern, dann
  `pip-compile --generate-hashes --allow-unsafe --strip-extras -o tools/docs/requirements.txt tools/docs/requirements.in`
- Lint: in `tools/docs/` `npm install --save-exact --save-dev markdownlint-cli2@<version>`

## Was die CI macht (`.github/workflows/docs.yml`)

| Auslöser | Was passiert |
| --- | --- |
| Pull Request | Markdown-Lint, `mkdocs build --strict`, Link-Prüfung unter `/docs/dusk-dawn/` |
| Release `vX.Y.Z` veröffentlicht (keine Vorabversion) | Seite bauen, prüfen, `dusk-dawn-docs-X.Y.Z.zip` an das Release hängen |
| automatisches Release aus `release.yml` | wie oben, `release.yml` ruft den Workflow direkt auf |
| manuell (Actions → Docs → Run workflow, Tag angeben) | ZIP neu bauen und anhängen |

Es gibt keinen automatischen Deploy und keine Secrets.
