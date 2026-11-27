# elfjobs

Jobbörse für Studierende: Werkstudentenstellen und Kurzjobs, Firmen, Messen und Tags. Aktuell gibt es nur das Django-Admin.

Stack: Python 3.12, uv, Django 5.2, PostgreSQL 17, Docker Compose (Services `backend` und `db`).

## Voraussetzungen

- Docker Desktop
- Git
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

## Teamregeln

- Pakete nur mit `uv add <paket>` hinzufügen. Danach die Container mit `docker compose up --build` neu bauen.
- Arbeit in Feature-Branches, Änderungen per Pull Request in `main`.
- Jede Änderung kommt mit pytest-Tests. Tests ausführen: `docker compose exec backend uv run pytest`.
- Bei einem Konflikt in `uv.lock` eine Seite übernehmen und anschließend `uv lock` ausführen.
- Datenbank zurücksetzen: `docker compose down -v`. Das löscht alle Daten; danach `migrate` und `seed` erneut ausführen.
