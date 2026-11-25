# Contributing

## Bugs and wishes

Please report bugs and wishes as an [issue on GitHub](https://github.com/PXLJAKE/Dusk-Dawn/issues).

## Development

| What | How |
| --- | --- |
| Integration tests | `python -m pytest tests` (needs the packages from [`tests/requirements_test.txt`](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/tests/requirements_test.txt), including `pytest-homeassistant-custom-component`) |
| Sound core tests | `cd core && cargo test` |
| View the sidebar without Home Assistant | open [`custom_components/dusk_dawn/frontend/dev.html`](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/custom_components/dusk_dawn/frontend/dev.html) in a browser |
| Interfaces between sound core, integration, sidebar and sound lamp | [CONTRACT.md](https://github.com/PXLJAKE/Dusk-Dawn/blob/main/docs/CONTRACT.md) |

### Folders

| Folder | Content |
| --- | --- |
| `custom_components/dusk_dawn/` | Home Assistant integration |
| `core/` | sound core in Rust (Python package `dusk_dawn_core`) |
| `tests/` | integration tests |
| `docs/` | technical documentation in the repository |
| `website/` | sources of this documentation website (`de/`, `en/`) |
| `hardware/` | optional sound lamp |

## Pull requests and versions

Changes go to `main` via pull request. After every merge that changes the integration, a workflow bumps the patch version in `manifest.json` and publishes a GitHub release, which HACS offers as an update. For a bigger version jump (for example 0.4.0), raise the version in `manifest.json` in the pull request itself.

## Editing the docs

The pages live in `website/de/` and `website/en/`; every page exists in both languages with the same file name. To preview locally:

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r tools/docs/requirements.txt
mkdocs serve
```

Before opening a pull request, check (also runs in CI):

```bash
mkdocs build --strict
npm ci --prefix tools/docs && tools/docs/node_modules/.bin/markdownlint-cli2
```

!!! warning "Open"
    There is no CONTRIBUTING file, no code of conduct and no agreed code style rules yet.
