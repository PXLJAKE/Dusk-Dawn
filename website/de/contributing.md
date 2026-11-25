# Mitmachen

## Fehler und Wünsche

Fehler und Wünsche bitte als [Issue auf GitHub](https://github.com/PXLJAKE/Dusk-Dawn/issues) melden.

## Entwicklung

| Was | Wie |
| --- | --- |
| Tests der Integration | `python -m pytest tests` (braucht die Pakete aus [`tests/requirements_test.txt`](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/tests/requirements_test.txt), u. a. `pytest-homeassistant-custom-component`) |
| Tests des Klangkerns | `cd core && cargo test` |
| Seitenleiste ohne Home Assistant ansehen | [`custom_components/dusk_dawn/frontend/dev.html`](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/custom_components/dusk_dawn/frontend/dev.html) im Browser öffnen |
| Schnittstellen zwischen Klangkern, Integration, Seitenleiste und Soundlampe | [CONTRACT.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/docs/CONTRACT.md) |

### Ordner

| Ordner | Inhalt |
| --- | --- |
| `custom_components/dusk_dawn/` | Home-Assistant-Integration |
| `core/` | Klangkern in Rust (Python-Paket `dusk_dawn_core`) |
| `tests/` | Tests der Integration |
| `docs/` | technische Doku im Repository |
| `website/` | Quellen dieser Doku-Website (`de/`, `en/`) |
| `hardware/` | optionale Soundlampe |

## Pull Requests und Versionen

Änderungen kommen per Pull Request auf `main`. Nach jedem Merge, der die Integration ändert, erhöht ein Workflow automatisch die Patch-Version in `manifest.json` und veröffentlicht ein GitHub-Release, das HACS als Update anbietet. Für einen größeren Versionssprung (zum Beispiel 0.4.0) die Version in `manifest.json` im Pull Request selbst erhöhen.

## Doku bearbeiten

Die Seiten liegen unter `website/de/` und `website/en/`, jede Seite gibt es in beiden Sprachen mit gleichem Dateinamen. Lokal ansehen:

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r tools/docs/requirements.txt
mkdocs serve
```

Vor dem Pull Request prüfen (läuft auch in der CI):

```bash
mkdocs build --strict
npm ci --prefix tools/docs && tools/docs/node_modules/.bin/markdownlint-cli2
```

!!! warning "Offen"
    Es gibt bisher keine CONTRIBUTING-Datei, keinen Code of Conduct und keine festgelegten Code-Stil-Regeln.
