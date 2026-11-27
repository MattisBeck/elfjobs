# AGENTS.md

## Vision

elfjobs ist die Jobbörse für **kurze Jobs neben dem Studium**: Werkstudentenstellen und Kurzjobs mit wenigen Stunden pro Woche. Beide Seiten wissen, woran sie sind: Firmen suchen Studierende, Studierende binden sich nicht für Jahre. Die Hürde, einen Job anzufangen, soll so niedrig sein wie bei Too Good To Go, nicht so förmlich wie bei LinkedIn oder Indeed.

**Kern der Idee** (Ideen-Dashboard der Gruppe): *Stundenplan × Lehrplan = Job.* Das Problem ist der schwere Einstieg in einen Job. Der Stundenplan zeigt, ob jemand Zeit für eine Stelle hat. Der Lehrplan, also was im Studium unterrichtet wird, zeigt, ob jemand schon qualifiziert ist oder es bald sein wird. Beides fließt in die Sortierung der Jobs ein (#41, #42). Firmen erreichen so Studierende direkt aus ihrer Branche.

**Für wen** (Personas aus den Interviews, siehe Protokoll vom Kick-off):

- **Julia**, 18, Politikwissenschaft: finanziert ihr Studium selbst und hat wenig Zeit. Sie braucht Geld, aber auch Zeit zum Studieren, und Arbeitszeiten, die planbar in ihre Woche passen.
- **Justus**, 19, BWL: wird von den Eltern finanziert und will Berufserfahrung sammeln. Er sucht einen einfachen Weg zu einem Job in seinem Bereich.

Aus den Interviews: Zeitmangel und Planbarkeit sind das größte Problem. Viele kommen über Bekannte an Jobs und lernen Firmen lieber persönlich kennen als online. Lange Pendelzeit frisst den Lohn auf.

**Priorität der Features** (Ranking der Gruppe nach Nutzen und Umsetzbarkeit):

1. Sortieren nach Distanz, Stundenlohn inklusive Pendelzeit und Bewertung (#12, #22, #32)
2. Lehrpläne und Closed Access ⭐: Registrieren nur mit Uni-Mail, zum Start nur HPI (#6, #31). Aus belegten Modulen folgen Skills (wer PT1 belegt hat, kann C-Grundlagen), damit sich Studierende mehr zutrauen und Arbeitgeber nach Skills suchen können (#30, #40, #41).
3. Eventhub: Jobmessen und Events, Alerts für passende Jobs (#33, #34)
4. Wiki zu Bürokratie und Bewerbung, von Studierenden geschrieben
5. Stundenplan eintragen oder hochladen und Jobs finden, die hineinpassen ⭐ (#7, #9, #43)
6. Karte: Wo sind Jobs in meiner Nähe? (#20, #21)

⭐ = im Protokoll auf dem Whiteboard rot markiert.

Die Oberfläche folgt der Designrichtung A „Wochenplan“ (`docs/design.md`).

**Ideen und Hintergrund:** `docs/ideen.md` (Problem, Personas, Interview-Erkenntnisse, Ranking, Ideenspeicher mit Status jeder Idee). Lies es, bevor du ein Feature-Issue anlegst oder eine Produktentscheidung triffst. Neue Issues zu einer Idee trägst du dort im Ideenspeicher ein.

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
