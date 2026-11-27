# AGENTS.md

## Vision

elfjobs bringt Studierende und Arbeitgeber für Nebenjobs zusammen: Werkstudentenstellen und Kurzjobs. Studierende sollen schnell sehen, welche Stelle wirklich zu ihnen passt. Dafür zählen ihr Stundenplan, ihre Skills und ihr Studiengang und der effektive Stundenlohn, nicht nur der Bruttolohn. Firmen und Jobmessen verbinden Online-Suche und persönliches Kennenlernen.

Geplante Bausteine, in etwa in dieser Reihenfolge: Frontend zum Durchsuchen der Stellen, Login und Studi-Profile, Stundenplan und Verfügbarkeiten, Bewerbungen, Matching, effektiver Stundenlohn.

## Arbeitsweise

- **Minimal**: Baue genau das, was die aktuelle Aufgabe verlangt. Fünf Studierende sollen jede Zeile verstehen können, deshalb lieber einfacher, expliziter Django-Code als neue Abstraktionen.
- Code-Bezeichner auf Englisch, Anzeige-Labels (`verbose_name`, Choices, Admin) und README auf Deutsch.
- Konfiguration und Secrets kommen aus Umgebungsvariablen (`.env`, Vorlage `.env.example`).
- Fasse nur die Dateien an, die zur Aufgabe gehören. Was dir darüber hinaus auffällt, meldest du zurück.

## Git: Branches und Pull Requests

`main` ändert sich nur durch gemergte Pull Requests.

- Vor jeder Änderung einen eigenen Branch von aktuellem `main` anlegen: `git switch main && git pull && git switch -c <typ>/<kurzbeschreibung>` (z. B. `feature/stellen-liste`, `fix/seed-loehne`, `docs/readme`).
- Commits und Pushes gehen auf diesen Branch, dann Pull Request in `main`.
- Gemergt wird erst, wenn die Tests grün sind.

## Portabilität: fünf Rechner, ein Setup

Fünf Leute arbeiten parallel auf macOS, Windows (WSL2) und Linux. Das Projekt muss auf jedem Rechner nur mit Docker und Git starten, und zwar mit genau den Schritten aus dem README.

- Alles läuft im Container: `docker compose exec backend uv run ...`. Lokal ist uv nur für die Editor-Autovervollständigung da.
- Keine Pfade, Ports oder Werkzeuge, die nur auf deinem Rechner existieren. Dateipfade im Code relativ zu `BASE_DIR`.
- Jede neue Umgebungsvariable kommt mit Platzhalter in `.env.example`. Jeder neue Setup-Schritt kommt ins README (Abschnitt „Erster Start“ oder „Häufige Probleme“).
- Demo-Daten nur über `seed`, deterministisch, damit alle dasselbe sehen. Wenn du ein Model erweiterst, ergänze `seed`.
- Zeilenenden sind LF (`.gitattributes`).

## Pakete: nur uv

- Neue Pakete nur mit `uv add <paket>`, Dev-Werkzeuge mit `uv add --dev <paket>`. Dadurch bleiben `pyproject.toml` und `uv.lock` synchron. Beide gehören in denselben Commit.
- Nach einer Paketänderung das Image neu bauen: `docker compose up --build`.
- Bei einem Konflikt in `uv.lock`: eine Seite übernehmen, dann `uv lock`.

## Tests: pytest

Jede Änderung an Verhalten kommt mit pytest-Tests (`pytest-django`). Eine Aufgabe ist erst fertig, wenn die neuen Tests geschrieben sind und die ganze Suite im Container grün ist:

```
docker compose exec backend uv run pytest
```

- Tests liegen pro App unter `<app>/tests/test_*.py` (Vorbild: `jobs/tests/test_seed.py`).
- Datenbank-Tests markierst du mit `@pytest.mark.django_db`. Sie laufen gegen eine eigene Test-Datenbank in Postgres, die echten Daten bleiben unberührt.
- Schreib Testfunktionen im pytest-Stil mit `assert`, keine `unittest.TestCase`-Klassen.
- Bei einem Bugfix zuerst einen Test schreiben, der den Fehler zeigt, dann den Fix.

Vor dem Commit außerdem: `docker compose exec backend uv run python manage.py check`. Nach Model-Änderungen `makemigrations` ausführen und die Migration mit committen.
