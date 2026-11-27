# elfjobs

Jobbörse für Studierende: Werkstudentenstellen und Kurzjobs, Firmen, Messen und Tags. Aktuell gibt es nur das Django-Admin.

Stack: Python 3.12, uv, Django 5.2, PostgreSQL 17, Docker Compose (Services `backend` und `db`).

## Voraussetzungen

- Docker Desktop (macOS, Windows, Linux). Auf macOS geht auch [Colima](https://github.com/abiosoft/colima) (`brew install colima docker docker-compose`, dann `colima start`).
- Windows: Repo innerhalb von WSL2 klonen und dort arbeiten (nicht unter `C:\`), sonst ist der Bind-Mount langsam.
- Git
- GitHub CLI (`gh`), danach einmal `gh auth login`. Damit arbeiten wir mit Issues und Pull Requests (siehe `CLAUDE.md`).
- Optional, nur für die Claude-Code-Werkzeuge (siehe unten): Node.js 20 oder neuer (Taste: 22) und Google Chrome. Für das Projekt selbst reichen Docker und Git.
- uv (nur für die Autovervollständigung im Editor): lokal `uv sync` ausführen, das erzeugt `.venv`. Dieses `.venv` im Editor als Interpreter auswählen.

## Erster Start

1. Umgebungsdatei anlegen:

   ```
   cp .env.example .env
   ```

2. Container bauen und starten:

   ```
   docker compose up --build
   ```

3. In einem zweiten Terminal die Datenbank migrieren:

   ```
   docker compose exec backend uv run python manage.py migrate
   ```

4. Demo-Daten anlegen (5 Messen, 20 Firmen, 15 Tags, 200 Stellen):

   ```
   docker compose exec backend uv run python manage.py seed
   ```

5. Admin-Benutzer anlegen:

   ```
   docker compose exec backend uv run python manage.py createsuperuser
   ```

Danach ist das Admin unter http://localhost:8000/admin erreichbar. Ein Frontend gibt es noch nicht.

Demo-Login für die Seite: `mia@student.hpi.uni-potsdam.de` mit dem Passwort `DEMO_PASSWORD` aus `.env`. Registrieren geht zum Start nur mit HPI-Mail (`UNI_EMAIL_DOMAINS` in `config/settings.py`).

Jede Person hat ihre eigene lokale Datenbank. `seed` erzeugt bei allen dieselben Demo-Daten, den Admin-Benutzer legt jede Person selbst an.

## Claude Code

Das Repo bringt Werkzeuge für Claude Code mit, die nach `git pull` automatisch da sind:

- **Design-Skills** in `.claude/skills/`, kopiert aus den Upstream-Repos am 27.11.2026, ohne Änderungen:
  - `/impeccable` (Design, Kritik, Feinschliff), Version 4.11.1, [pbakaus/impeccable](https://github.com/pbakaus/impeccable). Lädt beim ersten Aufruf sein Programm (Engine) von den GitHub-Releases nach `~/.impeccable/` und prüft es per SHA-256. Dafür braucht es Internet und `curl` oder `wget`.
  - `design-taste-frontend` (Taste), Version 2.5.1, [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill). Enthält einen Stop-Hook: Ist der Skill aktiv, prüft er beim Beenden die Seite in Chrome (`node gate.mjs`, bis zu 10 min) und kann das Beenden blockieren. Braucht Node 22.
  - Emil Kowalskis Skills zu Animation und UI, z. B. `/emil-design-eng`, `/review-animations` ([emilkowalski/skill](https://github.com/emilkowalski/skill)).
- **Playwright** (`.mcp.json`, Version 0.0.86): Claude kann damit die Seite im Browser öffnen, klicken und Screenshots machen. Der Browser läuft mit eigenem, flüchtigem Profil (`--isolated`) und lädt nur `localhost:8000` und Google Fonts (`--allowed-origins`, laut Playwright keine harte Sicherheitsgrenze). Er nutzt das installierte Google Chrome. Beim ersten Start fragt Claude Code, ob es den Server aus `.mcp.json` verwenden darf; mit Ja bestätigen.

## Häufige Probleme

- `seed` meldet `DEMO_PASSWORD fehlt`: Die Zeile `DEMO_PASSWORD=…` aus `.env.example` in deine `.env` kopieren, dann `docker compose up -d` (lädt die `.env` neu).
- `docker-credential-desktop: executable file not found`: In `~/.docker/config.json` die Zeile `"credsStore": "desktop"` löschen (Überbleibsel einer alten Docker-Desktop-Installation).
- Colima, Backend stoppt mit `can't open file '/app/manage.py'`: Das Repo muss unter deinem Home-Verzeichnis liegen, Colima gibt nur das an Docker weiter.
- Port 8000 belegt: Das andere Programm beenden, das auf Port 8000 läuft.
- Linux: Dateien, die im Container entstehen (z. B. Migrationen), gehören `root`. Danach `sudo chown -R $USER .` ausführen.

## Teamregeln

- Pakete nur mit `uv add <paket>` hinzufügen. Danach die Container mit `docker compose up --build` neu bauen.
- Nie direkt auf `main` arbeiten. Für jede Änderung einen eigenen Branch anlegen (`git switch -c feature/<name>`), pushen und per Pull Request in `main` mergen.
- Jede Änderung kommt mit pytest-Tests. Tests ausführen: `docker compose exec backend uv run pytest`.
- Bei einem Konflikt in `uv.lock` eine Seite übernehmen und anschließend `uv lock` ausführen.
- Datenbank zurücksetzen: `docker compose down -v`. Das löscht alle Daten; danach `migrate` und `seed` erneut ausführen.
