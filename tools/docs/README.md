# Doku-Website: Bauen, Release-ZIP und Deploy auf Plesk

Die Doku-Website entsteht mit MkDocs (Material-Theme) aus `website/de/` und `website/en/`, Einstellungen in [`mkdocs.yml`](../../mkdocs.yml). Ziel ist `https://<deine-domain>/docs/dusk-dawn/`.

## Lokal bauen

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r tools/docs/requirements.txt
mkdocs serve                                                    # Vorschau auf http://127.0.0.1:8000/
DOCS_URL=https://<deine-domain>/docs/dusk-dawn/ mkdocs build --strict   # fertige Seite in site/
```

`DOCS_URL` setzt `site_url` (Sitemap, Canonical-Links). Ohne `DOCS_URL` sind alle Links relativ, die Seite funktioniert dann in jedem Unterordner.

Markdown-Lint: `npm ci --prefix tools/docs && tools/docs/node_modules/.bin/markdownlint-cli2`

Versionen aktualisieren: Versionen in `requirements.in` ändern, dann
`pip-compile --generate-hashes --allow-unsafe --strip-extras -o tools/docs/requirements.txt tools/docs/requirements.in`;
für den Lint `npm install --save-exact --save-dev markdownlint-cli2@<version>` in `tools/docs/`.

## Was die CI macht (`.github/workflows/docs.yml`)

| Auslöser | Was passiert |
| --- | --- |
| Pull Request | Markdown-Lint und `mkdocs build --strict` |
| Release `vX.Y.Z` veröffentlicht (keine Vorabversion) | Seite bauen, `dusk-dawn-docs-X.Y.Z.zip` an das Release hängen, optional Deploy |
| automatisches Release aus `release.yml` | wie oben, `release.yml` ruft den Workflow direkt auf |
| manuell (Actions → Docs → Run workflow, Tag angeben) | ZIP neu anhängen und neu deployen |

Die ZIP enthält den Inhalt der Seite direkt (ohne Unterordner). Entpackt in `<docroot>/docs/dusk-dawn/` ist sie sofort online.

## Deploy auf Plesk einrichten

Der Deploy-Job läuft nur, wenn **alle fünf** Secrets gesetzt sind. Fehlt eins, wird er mit einem Hinweis übersprungen, die ZIP am Release gibt es trotzdem.

### 1. SSH-Zugang für den Subscription-User in Plesk

1. In Plesk **Websites & Domains → deine Domain → Hosting & DNS → Hosting** (in älteren Versionen **Hosting-Einstellungen**) öffnen.
2. Bei **SSH-Zugriff** `/bin/bash` wählen und speichern. Mit `/bin/bash (chrooted)` geht es nur, wenn `rsync` in der chroot-Umgebung vorhanden ist; das bitte einmal per SSH mit `rsync --version` prüfen.
3. Notiere dir den **Benutzernamen** der Subscription (steht auf derselben Seite, z. B. `meinedomain_xyz`). Das ist `DOCS_DEPLOY_USER`.

### 2. Schlüsselpaar nur für den Deploy erzeugen

Auf deinem Rechner, ohne Passphrase (GitHub Actions kann keine eingeben):

```bash
ssh-keygen -t ed25519 -N "" -C "github-actions dusk-dawn docs" -f dusk-dawn-docs
```

Das ergibt `dusk-dawn-docs` (privat, kommt als Secret zu GitHub) und `dusk-dawn-docs.pub` (öffentlich, kommt nach Plesk).

### 3. Öffentlichen Schlüssel in Plesk hinterlegen

- **Mit der Erweiterung „SSH Keys Manager“:** **Websites & Domains → deine Domain → SSH-Schlüssel → SSH-Schlüssel hinzufügen**, Inhalt von `dusk-dawn-docs.pub` einfügen. Fehlt der Eintrag, kann der Plesk-Admin die kostenlose Erweiterung unter **Erweiterungen** installieren.
- **Ohne Erweiterung:** einmal mit Passwort per SSH als Subscription-User anmelden und den Schlüssel anhängen:

  ```bash
  mkdir -p ~/.ssh && chmod 700 ~/.ssh
  cat >> ~/.ssh/authorized_keys      # Inhalt von dusk-dawn-docs.pub einfügen, dann Strg+D
  chmod 600 ~/.ssh/authorized_keys
  ```

Test vom eigenen Rechner: `ssh -i dusk-dawn-docs <user>@<host> pwd`. Die Ausgabe zeigt auch, wie Pfade für diesen User aussehen (wichtig für Schritt 5).

### 4. Host-Key festhalten (für die strikte Prüfung)

```bash
ssh-keyscan -t ed25519 <host> > known_hosts_docs
ssh-keygen -lf known_hosts_docs        # Fingerabdruck anzeigen
```

Vergleiche den Fingerabdruck mit dem echten Server-Schlüssel, zum Beispiel per `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` auf dem Server oder mit dem, den dir dein Hoster nennt. Nur wenn er übereinstimmt, kommt der Inhalt von `known_hosts_docs` als Secret zu GitHub. Die Host-Key-Prüfung wird im Workflow nie abgeschaltet: stimmt der Schlüssel nicht, bricht der Deploy ab.

### 5. Zielordner bestimmen

Der Zielordner ist der volle Pfad `<docroot>/docs/dusk-dawn`. Bei Plesk liegt das Docroot meist unter `/var/www/vhosts/<domain>/httpdocs`, also:

```text
/var/www/vhosts/<domain>/httpdocs/docs/dusk-dawn
```

Bei einem chroot-Zugang kann der Pfad anders aussehen (zum Beispiel `/httpdocs/docs/dusk-dawn`); maßgeblich ist, was `pwd` in Schritt 3 zeigt. Der Ordner wird beim ersten Deploy angelegt.

Der Workflow lehnt einen leeren Pfad, `/`, Pfade mit `..` und jeden Pfad ab, der **nicht auf `/docs/dusk-dawn` endet**. So kann `rsync --delete` nur diesen einen Ordner leeren und nie das restliche Docroot deiner Entwickler-Website.

### 6. Secrets in GitHub setzen

Im Repository **Settings → Secrets and variables → Actions → Secrets → New repository secret**:

| Secret | Inhalt |
| --- | --- |
| `DOCS_DEPLOY_HOST` | Hostname des Plesk-Servers, z. B. `server.example.com` |
| `DOCS_DEPLOY_USER` | Subscription-User aus Schritt 1 |
| `DOCS_DEPLOY_KEY` | kompletter Inhalt der privaten Datei `dusk-dawn-docs` (inklusive `-----BEGIN …` und `-----END …`) |
| `DOCS_DEPLOY_PATH` | Zielordner aus Schritt 5 |
| `DOCS_DEPLOY_KNOWN_HOSTS` | Inhalt von `known_hosts_docs` aus Schritt 4 |

Unter **Variables → New repository variable** optional `DOCS_URL` = `https://<deine-domain>/docs/dusk-dawn/` setzen (für Sitemap und Canonical-Links).

SSH läuft über Port 22. Danach die privaten Schlüsseldateien auf deinem Rechner löschen oder sicher verwahren.

### 7. Ausprobieren

**Actions → Docs → Run workflow**, als Tag ein vorhandenes Release angeben, das die Doku schon enthält (also eines nach dem Merge dieses Pull Requests). Danach sollte `https://<deine-domain>/docs/dusk-dawn/` erreichbar sein.
