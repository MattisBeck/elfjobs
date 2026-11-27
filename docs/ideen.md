# Ideen und Hintergrund

Alles, was wir in der Gruppensitzung (26. und 27.11.2026) zur Produktidee erarbeitet haben: Problem, Personas, Erkenntnisse aus den Interviews, Ranking und **alle** Ideen, auch die verworfenen. Die Kurzfassung steht in `CLAUDE.md` unter „Vision“, das Design in `docs/design.md`.

Lies das hier, bevor du ein Feature-Issue anlegst oder eine Produktentscheidung triffst. Entschieden wird in Issues. Hier steht, warum. Wenn ein Issue zu einer Idee entsteht oder eine Idee verworfen wird, trag es im [Ideenspeicher](#ideenspeicher) ein.

## Das Problem

Aus dem Ideen-Dashboard (Tag 2):

- **Angst, einen Job anzufangen.** Viele trauen sich nicht, weil sie glauben, sie hätten nichts zu bieten oder ihnen fehlten Skills.
- **Zerstückelte Freizeit.** Zwischen Vorlesungen bleiben nur Lücken, und klassische Jobs passen nicht hinein.

Zusammen ergibt das die Hürde: Der Einstieg in einen Job ist schwer.

## Die Kernidee: Stundenplan × Lehrplan = Job

- **Stundenplan:** zeigt, ob jemand Zeit für eine Stelle hat. Schichten werden mit den Vorlesungen abgeglichen, inklusive Fahrzeit.
- **Lehrplan:** zeigt, was im Studium unterrichtet wird, also ob jemand schon qualifiziert ist oder es bald sein wird. Wer am HPI PT1 belegt hat, kann C-Grundlagen und Memory Management, auch wenn es nicht im Lebenslauf steht. Arbeitgeber suchen nach diesen Skills, und Studierende trauen sich mehr zu.

Beides fließt in die Sortierung der Stellen ein („Passt am besten“, #42).

## Positionierung

- **Nur kurze Jobs:** Werkstudentenstellen und Kurzjobs mit wenigen Stunden pro Woche. Firmen wissen, dass sie Studierende bekommen. Studierende wissen, dass niemand erwartet, dass sie jahrelang bleiben.
- **Niedrige Hürde, wie bei Too Good To Go:** kurzfristig und unkompliziert, nicht so förmlich wie LinkedIn oder Indeed.
- **Idee für ein Siegel:** „zeitlich flexible Jobs für Studierende“ für Firmen, die sich auf Stundenpläne einlassen.
- **Für Studierende kostenlos.**

## Für wen: Personas

| | Julia | Justus |
|---|---|---|
| Alter, Studium | 18, Politikwissenschaft | 19, BWL |
| Finanzierung | muss ihr Studium selbst finanzieren, erste Studierende in der Familie | wird von den Eltern finanziert, Eltern sind Akademiker\*innen |
| Braucht | Geld zum Leben, aber auch Zeit zum Studieren. Wenig Zeit, sonst leidet das Studium. Sucht irgendwas, Hauptsache Geld (nicht unbedingt im späteren Arbeitsbereich). | Berufserfahrung (Employability), Geld für Urlaub mit Freunden. Kann es sich leisten, für Erfahrung zu arbeiten und länger zu studieren. |
| Paradox | mehr arbeiten heißt weniger Zeit für die Uni, die Uni ist ihr aber wichtig | ohne Berufserfahrung kein Job, ohne Job keine Berufserfahrung |
| Wir helfen durch | Planbarkeit: Arbeitszeiten, die genau in die Freizeit passen. Lernen und Job in einem. | einen einfachen Weg zu einem Job in seinem Bereich |

## Erkenntnisse aus den Interviews

Fünf Interviews, die Erkenntnisse geclustert:

- **Zeitmangel:** Zeitprobleme für einen Job, oft nur kurze Freizeiten, Selbsteinteilung ist wichtig. Lange Pendelzeit (bis 1 h) frisst den Lohn auf.
- **Unsicherheit:** „Ich hab ja nichts zu bieten“, „Hat Gefühl, nutzlos zu sein“. Bürokratie schreckt ab: Minijob-Grenze, Versicherungen.
- **Jobquelle:** Jobs werden oft zufällig oder über Bekannte gefunden. Firmen lernt man lieber persönlich als online kennen. Manche kennen keine Jobportale.
- **Motivation Geld:** von „notwendig, sonst kein Geld“ (Callcenter) bis „von den Eltern finanziert, keine Geldnot“.
- **Motivation Erfahrung:** Erfahrung ist manchen wichtiger als Geld. Der Job soll zum späteren Beruf passen. Verschiedene Sachen ausprobieren.

Zitate, die wir oft wieder aufgreifen:
- „Flexibilität ist am wichtigsten.“
- „Der Job sollte nicht zu weit entfernt liegen.“
- „Der Mindestlohn ist ziemlich hoch.“
- „Das Wichtigste ist an einem Job, dass er Spaß macht und man neue Erfahrungen sammeln kann.“

## Ranking der Gruppe

Bewertet nach Nutzen für Studierende und Umsetzbarkeit. Jede Person hatte Punkte für ihre wichtigsten Features.

| Platz | Feature | Punkte | Issues |
|---|---|---|---|
| 1 | Sortieren nach Distanz, Stundenlohn inkl. Pendelzeit, Bewertung | 3 | #12, #22, #32 |
| 2 | Lehrpläne und Closed Access ⭐ | 3 | #6, #30, #31, #40, #41, #50 |
| 3 | Eventhub, dazu Alerts für passende Jobs | 3 | #33, #34 |
| 4 | Wiki mit Guides von Studierenden, evtl. KI-Bot | 3 | noch keins |
| 5 | Stundenplan eintragen und passende Jobs finden ⭐ | 2 | #7, #9, #10, #11, #43 |
| 6 | Karte: Wo sind Jobs in meiner Nähe? | 2 | #20, #21 |

⭐ = im Protokoll auf dem Whiteboard rot markiert.

## Ideenspeicher

Alle Ideen aus der Ideenschmiede und vom Ranking-Board. Status: **Issue** = wird gebaut oder ist geplant, **offen** = noch kein Issue, **verworfen** = bewusst nicht.

| Idee | Status |
|---|---|
| Stundenplan angeben → passende Jobs finden | Issue #7, #9, #43, #87 (eintragen wie im Kalender) |
| Planbarkeit: Schichten über die Plattform abstimmen | Issue #10, #11 |
| Effektiver Stundenlohn inkl. Pendelzeit | Issue #12 |
| Lehrpläne: Skills aus belegten Modulen | Issue #30, #40, #41 |
| Badge „Du bist qualifiziert“ gegen die Angst vorm Bewerben | Issue #86, Wording #98 |
| Skills aus dem Lebenslauf | Issue #50 |
| Matching / „Jobfindealgorithmus“ | Issue #42 |
| Closed Access, Account-Verifikation per Uni-Mail | Issue #6, #31 |
| Bewertungen für Arbeitnehmer und Arbeitgeber (nur positiv); dazu echte anonyme Bewertungen (nur wenn man sicher da gearbeitet hat) | Issue #32 |
| Eventhub („Online-Schwarzes-Brett“), Jobmessen | Issue #33 |
| Alerts, wenn passende Jobs erscheinen | Issue #34 |
| Onboarding: Was machst du, wann hast du Zeit, Erfahrungen, Interessen | Issue #35 |
| Sehen, welche Jobs Freunde gemacht haben | Issue #36 |
| Firmen verlinken Social Media, Sharepic-Generator | Issue #37 |
| Lebenslauf auf der Plattform hochladen | Issue #38 |
| Karte „Wo sind Jobs in meiner Nähe?“, Distanz | Issue #20, #21, #22 |
| Mit Profil bewerben | Issue #14 |
| Wiki zu Bürokratie, Bewerbung usw. von Studierenden, mit Belohnung | offen (Platz 4) |
| KI-Bot zum Wiki | offen |
| Branchenwünsche im Profil | offen |
| Personen für Jobs vorschlagen | offen |
| Probearbeiten per Klick anfragen | offen |
| Speeddating mit Unternehmen | offen |
| Jobs wie bei Tinder swipen | offen |
| „Wege zu uns und weiter zum Job“ | offen, Bedeutung unklar |
| Werbung für die Plattform: Banner bei Events | offen (Marketing, kein Feature) |
| Anzeigen schalten als Einnahmequelle | offen, wenig Nutzen für Studierende |
| Gamification, Streaks, Roadmap „Trophäenpfad“, Achievements (erste Bewerbung, erster Job, erstes Zertifikat) | zurückgestellt: schwer umsetzbar, wenig Nutzen |
| ELO-Rating für Studierende | verworfen 👎 |
| Bürokratie abbauen (Ideenschmiede) | offen, hängt mit dem Wiki zusammen (Platz 4) |
| Finanzierungs-Checks: Plattform prüft automatisch BAföG, Stipendien und Wohngeld | offen (schwer machbar, hoher Nutzen) |
| Jobs an der Uni als Praktikum anrechnen | offen (schwer machbar, hoher Nutzen) |
| Karriereplanung: Traumjob angeben, Plattform stellt Portfolio vor und schlägt Jobs vor, die darauf vorbereiten | offen (schwer machbar) |
| Auswirkungen auf Steuern und Versicherungen transparent angeben | offen (hoher Nutzen) |
| Studiengänge einer Uni/Stadt im Profil festlegen, als Filter für Jobs | offen |
| Klausurphasen-Modus: „In dieser Zeit keine Jobs“ | offen |
| Nur nach unbefristeten Stellen filtern | offen |

## Go-to-Market

- **Unfair Advantage:** Partnerschaften mit bestimmten Hochschulen. Zum Start nur das HPI (Closed Access, #6). Ob es schon Partnerschaften gibt oder ob sie ein Ziel sind, ist offen.
- **Unfair Advantage, zweiter Punkt:** Arbeitgeber können sich sicher sein, dass die Studierenden einen Job in dieser Branche wollen und es um Erfahrung geht, nicht primär ums Geld.
- **Start lokal:** Bei Unternehmens-Messen: „Schaut euch unsere Seite an und stellt eure Jobs dort ein.“ An Universitäten: Studierenden sagen, dass sie bei uns Jobs finden können.
- **USP:** Unternehmen wollen vielleicht nur Studierende ausgewählter Top-Unis und können sich so auf deren Qualität verlassen.
- Firmen erreichen über uns Studierende direkt aus ihrer Branche und mit passenden Skills.

## Offene Fragen

- Was genau ist mit „Wege zu uns und weiter zum Job“ gemeint?
- Wiki (Platz 4): Wer schreibt es, wie sieht die Belohnung aus?
- Welche Hochschulen kommen nach dem HPI?
