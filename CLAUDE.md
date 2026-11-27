# AGENTS.md

## Vision

elfjobs bringt Studierende und Arbeitgeber für Nebenjobs zusammen: Werkstudentenstellen und Kurzjobs. Studierende sollen schnell sehen, welche Stelle wirklich zu ihnen passt. Dafür zählen ihr Stundenplan, ihre Skills und ihr Studiengang und der effektive Stundenlohn, nicht nur der Bruttolohn. Firmen und Jobmessen verbinden Online-Suche und persönliches Kennenlernen.

Geplante Bausteine, in etwa in dieser Reihenfolge: Frontend zum Durchsuchen der Stellen, Login und Studi-Profile, Stundenplan und Verfügbarkeiten, Bewerbungen, Matching, effektiver Stundenlohn.

## Arbeitsweise

- **Minimal**: Baue genau das, was die aktuelle Aufgabe verlangt. Fünf Studierende sollen jede Zeile verstehen können, deshalb lieber einfacher, expliziter Django-Code als neue Abstraktionen.
- Code-Bezeichner auf Englisch, Anzeige-Labels (`verbose_name`, Choices, Admin) und README auf Deutsch.
- Konfiguration und Secrets kommen aus Umgebungsvariablen (`.env`, Vorlage `.env.example`).
- Fasse nur die Dateien an, die zur Aufgabe gehören. Was dir darüber hinaus auffällt, meldest du zurück.

## Zusammenarbeit: Issue → Branch → Pull Request

Fünf Leute arbeiten parallel. Die GitHub-Issues sind die einzige Liste dessen, was gerade gebaut wird. Wer einem Issue zugewiesen ist, arbeitet daran, alle anderen nicht.

1. **Issue klären**: `gh issue list` ansehen. Zu deiner Aufgabe gibt es ein Issue? Dann prüfe die Zuweisung. Es ist jemand anderem zugewiesen? Dann stopp und sprich mit der Person. Kein Issue vorhanden? Dann lege eines an (`gh issue create`): was gebaut wird, was ausdrücklich nicht dazugehört, woran man erkennt, dass es fertig ist.
2. **Reservieren**: Weise dir das Issue zu, bevor du Code schreibst (`gh issue edit <nr> --add-assignee @me`).
3. **Branch** vom aktuellen `main`: `git switch main && git pull && git switch -c <typ>/<nr>-<kurzbeschreibung>`, z. B. `feature/12-stellen-liste`, `fix/15-seed-loehne`. Commits und Pushes nie auf `main`; `main` ändert sich nur durch gemergte Pull Requests.
4. **Früh sichtbar machen**: Nach dem ersten Commit pushen und einen Draft-Pull-Request öffnen (`gh pr create --draft`), Beschreibung mit `Closes #<nr>`.
5. **Fertig**: Tests grün, Pull Request auf „Ready for review“, eine andere Person reviewt und merged.

Ein Issue ist **klein**: in ein bis zwei Tagen fertig. Größere Features werden in mehrere Issues geteilt. Wenn du merkst, dass deine Arbeit ein fremdes Issue berührt, schreib einen Kommentar dort.

**Gegenseitig pingen:** Menschen und ihre Claude-Agenten erwähnen sich mit `@login` in Issue- und PR-Kommentaren, zum Beispiel für ein Review, eine Frage zu einem fremden Issue oder eine Überschneidung. Im Team: `@MattisBeck`, `@Lille2008`, `@AuchHabicht`, `@ShadowAlyx`, `@Tobi-St`. Pingt auch zurück: Wer gepingt wird, antwortet im selben Thread mit `@login` der fragenden Person, damit die Antwort bei ihr ankommt. Wer etwas fertig hat, worauf jemand wartet (Review erledigt, PR gemergt, Frage geklärt), pingt diese Person an. Ein Ping ersetzt keine Zuweisung: An einem Issue, das jemand anderem gehört, arbeitest du erst nach Absprache.

**Migrationen** kollidieren, wenn zwei Branches gleichzeitig Migrationen in derselben App anlegen. Hole vor `makemigrations` den aktuellen `main` in deinen Branch (`git pull origin main`). Kommt nach dem Merge trotzdem ein Konflikt: deine eigene Migration löschen und `makemigrations` neu ausführen.

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
