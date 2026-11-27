# elfjobs

Jobbörse für Studierende: Werkstudentenstellen und Kurzjobs, Firmen, Messen und Tags. Aktuell gibt es nur das Django-Admin.

Stack: Python 3.12, uv, Django 5.2, PostgreSQL 17, Docker Compose (Services `backend` und `db`).

## Voraussetzungen

- Docker Desktop (macOS, Windows, Linux). Auf macOS geht auch [Colima](https://github.com/abiosoft/colima) (`brew install colima docker docker-compose`, dann `colima start`).
- Windows: Repo innerhalb von WSL2 klonen und dort arbeiten (nicht unter `C:\`), sonst ist der Bind-Mount langsam.
- Git
- GitHub CLI (`gh`), danach einmal `gh auth login`. Damit arbeiten wir mit Issues und Pull Requests (siehe `CLAUDE.md`).
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

Jede Person hat ihre eigene lokale Datenbank. `seed` erzeugt bei allen dieselben Demo-Daten, den Admin-Benutzer legt jede Person selbst an.

## Häufige Probleme

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
