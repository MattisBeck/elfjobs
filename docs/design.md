# Design: Richtung A „Wochenplan“

Das ist die Designrichtung, nach der wir die Oberfläche von elfjobs bauen. Sie wurde am 27.11.2026 aus drei Richtungen ausgewählt. **Maßgeblich ist dieses Dokument.** Der Canvas zeigt die Entwürfe zur Anschauung; wo beide voneinander abweichen, gilt der Text hier.

- Design-Canvas mit allen Entwürfen: https://claude.ai/artifact/9Z7g6PU9QA4gdbFkgha7HM (Zugriff bei Felix anfragen). Richtung A sind die Artboards „A · Wochenplan – Web“ und „A · Wochenplan – Handy“. Beide sind klickbar: In der Web-Ansicht wechseln die Tabs „Details“ und „In meiner Woche“, bei flexiblen Stellen lassen sich eigene Schichten in freie Blöcke legen.
- Issue zu diesem Dokument: #2
- Screenshots kommen in einem späteren PR nach `docs/img/`.

## Die Idee

**elfjobs: Stundenplan × Lehrplan = Job** (Ideen-Dashboard der Gruppe, HackWG 27.11.2026)

- **Problem:** Der Einstieg in einen Job ist für Studierende schwer.
- **Für wen:** Studierende mit wenig Zeit, die Interesse an einem Job in ihrer späteren Branche haben.
- **Was wir anbieten:** Eine Plattform zum Finden und Vergleichen von Minijobs und Werkstudentenstellen, keine Vollzeitjobs.
- **Für Studierende:** Der Abgleich mit dem **Stundenplan** zeigt schnell, ob sie Zeit für einen Job haben. Der **Lehrplan**, also was im Studium unterrichtet wird, zeigt, ob sie schon qualifiziert sind oder es bald sein werden.
- **Für Firmen:** Sie erreichen Studierende direkt aus ihrer Branche. Die Studierenden sammeln dort lieber Erfahrung als woanders mehr zu verdienen.
- **Umsetzung:** Stundenplan hochladen, Lehrplan einlesen, beides in die Sortierung der Jobs einrechnen, dazu ein kleiner Kalender pro Stelle.

In einem Satz: Studierende sehen bei jedem Job sofort, ob er in ihren Stundenplan passt, ob ihr Studium sie dafür qualifiziert und was pro Stunde wirklich übrig bleibt, wenn man die Fahrzeit mitrechnet.

## Prinzipien

- **Hell, ruhig, präzise.** Wirkt wie ein guter Uni-Kalender: weißer Grund, feine Linien statt Kästen, ein einziger Akzent (Blau).
- **Der Stundenplan ist eine Ansicht, kein Zwang.** Jede Stelle hat zwei Tabs: „Details“ (Standard) und „In meiner Woche“.
- **Ehrlich rechnen.** Neben dem Bruttolohn steht immer der effektive Lohn. Wie er entsteht, sieht man in der Lohnrechnung.
- **Zahlen sind Tabellenziffern.** Für alle Beträge und Uhrzeiten gilt `font-variant-numeric: tabular-nums`.
- **Farbe heißt Zustand.** Grün = Schicht passt, Rot = Konflikt, Orange = teilweise, Blau = flexibel bzw. deine eigene Schicht, Grau = Vorlesung.

## Farben

Als CSS-Variablen in einer statischen Datei anlegen (#3). Die Namen sind ein Vorschlag.

| Variable | Wert | Wofür |
|---|---|---|
| `--bg` | `#FFFFFF` | Seitengrund, Inhalt rechts |
| `--bg-subtle` | `#FAFBFC` | linke Spalte (Liste), Kopf der Wochenansicht |
| `--surface-muted` | `#F1F3F6` | Chips, aktive Navigation, Hintergrund der Tab-Leiste |
| `--line` | `#E6E8EC` | Trennlinien, Rahmen von Panels |
| `--line-strong` | `#E1E4E9` | Rahmen von Eingabefeldern und Knöpfen |
| `--ink` | `#1B1E25` | Text |
| `--ink-2` | `#3B404B` | Fließtext, Knopftext |
| `--muted` | `#646B78` | Metadaten, Labels |
| `--faint` | `#8A909C` | Uhrzeiten an der Kalenderachse |
| `--accent` | `#2F5BD8` | Hauptknopf, Wortmarke „jobs“, ausgewählte Zeile, eigene Schicht |
| `--accent-ink` | `#2A4FBF` | blauer Text auf hellem Blau |
| `--accent-soft` | `#EAF0FD` | Skill-Treffer, Avatar |
| `--accent-wash` | `#F3F6FE` | effektiver Lohn, freie Blöcke |
| `--lecture` | `#E9ECF1` | Vorlesungsblöcke |
| `--lecture-ink` | `#454B57` | Text in Vorlesungsblöcken |
| `--shift` | `#1F7A50` | passende Schicht (weißer Text) |
| `--ok-soft` / `--ok-ink` | `#E3F3EA` / `#1F6E48` | Pille „Passt in deine Woche“ |
| `--conflict` | `#C8402F` | kollidierende Schicht (weißer Text) |
| `--part-soft` / `--part-ink` / `--part-dot` | `#FCF0DE` / `#8F4C0A` / `#C77A1E` | „1 von 5 Schichten kollidiert“ |

## Schrift, Größen, Formen

- Schrift **Inter** (Google Fonts, Gewichte 400, 500, 600, 700), Fallback `system-ui, sans-serif`.
- Größen: 26 px Stellentitel, 20 px Seitenüberschrift, 19 px Wortmarke, 14 px Grundtext, 12–13 px Metadaten, 11 px Text im Kalender.
- Radien: 6 px Chips und Kalenderblöcke, 8 px Knöpfe und Eingabefelder, 10 px Listenzeilen, 12 px Panels, Tab-Leiste 9 px außen und 7 px innen, Filter-Chips rund (16 px).
- Abstände im 4-px-Raster, meistens 8, 12, 16, 20, 24.
- Klickflächen auf dem Handy mindestens 44 px hoch.

## Screens

### Kopfzeile (#3)

Wortmarke „elf**jobs**“ (der zweite Teil in `--accent`), Navigation „Jobs · Gemerkt · 2 · Messen“ (aktiver Punkt mit grauem Hintergrund), Suchfeld „Titel, Firma oder Skill“, rechts der Profil-Knopf mit Initiale im blauen Kreis, Name und „ITSE · 1. Semester“. Auf dem Handy: Zurück-Link, Wortmarke, Initiale.

### Stellenliste (#4, Passung #9, effektiver Lohn #12, Qualifikation #41, Sortierung #42)

Linke Spalte auf Desktop (380–460 px breit, Grund `--bg-subtle`), auf dem Handy eine eigene Seite.

- Überschrift „Jobs für deine Woche“, darunter „Wintersemester 2026/27 · 36 h frei zwischen 8 und 20 Uhr“.
- Filter-Chips: „Passt in meinen Plan“ (aktiv: dunkel gefüllt), „Werkstudent“, „Kurzjob“, „Remote“.
- Zeile „7 Stellen“ und die Sortierung. Standard für eingeloggte Studierende ist „Passt am besten“ (#42), sonst „effektiver Stundenlohn“.
- Pro Stelle eine Zeile: Titel (fett) und rechts der effektive Lohn (fett), darunter „Firma · Arbeitsort · 7 h/Woche“ und rechts „brutto 16,00 €“, darunter ein farbiger Punkt mit dem Passungstext und, durch „·“ getrennt, die Qualifikation („2 von 3 Anforderungen aus dem Studium“). Die ausgewählte Zeile hat einen weißen Hintergrund und einen blauen Rahmen.

### Stellendetail (#5)

Kopf: Chips (Art, Arbeitsort, „7 h pro Woche“), Titel, „Firma · Branche“, rechts die Knöpfe „Merken“ (Rahmen) und „Mit Profil bewerben“ (blau).

Darunter die **Tab-Leiste** im Stil eines Segmented Control: „Details“ | „● In meiner Woche“. Der Punkt vor „In meiner Woche“ hat die Passungsfarbe, so sieht man die Passung schon im Details-Tab. Im Prototyp schaltet `?ansicht=woche` um.

**Tab „Details“** (Standard):

- Links „Über die Stelle“ (Beschreibung aus der Anzeige), „Das bringst du mit“ (Skills als Chips, eingeordnet nach dem Lehrplan, siehe Regel „Qualifikation“: gelernt blau mit ✓ und der Quelle, z. B. „✓ Python · Programmiertechnik I“ oder „✓ Englisch · aus deinem Profil“; kommt noch grau mit „ab 3. Semester“; nicht im Studium grau ohne Zusatz) und ein Kasten „Firma persönlich kennenlernen: Jobmesse Potsdam 2027, 11.03.2027“ (ein Kasten für alle kommenden Messen der Firma, vergangene fallen weg).
- Rechts „Auf einen Blick“: Art, Arbeitsort, Stunden pro Woche, Arbeitszeiten („Di 15:00–18:30, Mi 16:30–20:00“ oder „Flexibel, du planst selbst“), Stundenplan (Passungstext als Link zum Wochen-Tab).
- Darunter die **Lohnrechnung** in vier Feldern: Bruttolohn pro Stunde · Fahrzeit pro Woche („2 × hin und zurück, je 18 min“) · **Effektiver Stundenlohn** (hellblau hinterlegt) · „Im Monat ≈ 485 €“ mit „unter/über der Minijob-Grenze (603 €)“.

### Tab „In meiner Woche“ (#10)

- Kopfzeile des Panels: Passungs-Pille links, Legende rechts (Vorlesung, Schicht, Konflikt, frei, deine Schicht).
- Kalender Montag bis Freitag, 8 bis 20 Uhr, 48 px pro Stunde, Achse alle 2 Stunden, feine Stundenlinien.
- Vorlesungen grau mit Titel und Uhrzeit. Schichten grün mit „Schicht“ und Uhrzeit. Kollidierende Schichten rot mit „Konflikt“. Schichtblöcke haben einen weißen Rand von 2 px, damit sie sich von Vorlesungen abheben.

### Flexible Stellen: eigene Schichten (#11)

- Bei Stellen ohne feste Zeiten zeigt die Woche die freien Blöcke gestrichelt blau („+ frei 15:00–20:00“).
- Antippen eines freien Blocks legt dort eine eigene Schicht an (im Canvas: bis zu 4 h ab Blockbeginn, höchstens die noch offenen Stunden). Sie erscheint blau gefüllt als „Deine Schicht“. Erneutes Antippen entfernt sie.
- Unter dem Kalender steht ein hellblauer Hinweis: „Flexible Zeiten: Tippe auf einen freien Block …“ und rechts „4 von 11 h verplant“.
- Im echten Formular wählt man Beginn und Ende innerhalb des Blocks.

### Handy

Gleicher Aufbau, eine Spalte: Kopf mit Zurück-Link, Stellentitel, darunter dieselbe Tab-Leiste. „Details“ zeigt oben die Lohnrechnung als 2×2-Raster, dann „Auf einen Blick“, Skills und Messe. „In meiner Woche“ zeigt den Kalender mit 30 px pro Stunde und Achse alle 4 Stunden. Unten fest: „Merken“ und „Mit Profil bewerben“.

### Merken und Bewerben (#13, #14)

„Merken“ wechselt zu „Gemerkt“, der Zähler in der Navigation steigt. „Mit Profil bewerben“ wird nach dem Klick zu „Bewerbung gesendet“ und ist danach deaktiviert.

## Regeln

### Freie Blöcke (#7)

Pro Tag die Lücken zwischen den Vorlesungen im Zeitraum 8 bis 20 Uhr, die **mindestens 2 Stunden** lang sind. Für die Demo-Studentin Mia: Mo 15:00–20:00, Di 12:30–20:00, Mi 12:30–20:00, Do 8:00–13:30 und 17:00–20:00, Fr 12:30–20:00, zusammen 36 h.

### Passung (#9)

Eine Schicht kollidiert, wenn sie sich mit einer Vorlesung desselben Tages überschneidet. Bei Stellen, die nicht remote sind, wird die Vorlesung um die einfache Fahrzeit nach vorn und hinten verlängert (man muss ja hinkommen). Eine Schicht, die genau dann beginnt, wenn die verlängerte Vorlesung endet, passt.

| Zustand | Bedingung | Text | Farbe |
|---|---|---|---|
| passt | feste Zeiten, keine Schicht kollidiert | „Passt in deine Woche“ | Grün |
| teilweise | einige, aber nicht alle Schichten kollidieren | „1 von 5 Schichten kollidiert“, ab zwei „2 von 5 Schichten kollidieren“ | Orange |
| kollidiert | alle Schichten kollidieren | „Kollidiert mit Vorlesungen“ | Rot |
| flexibel | Stelle ohne feste Zeiten | „Flexible Zeiten, du wählst die Schichten“ | Blau |

Der Filter „Passt in meinen Plan“ zeigt „passt“ und „flexibel“.

### Effektiver Stundenlohn (#12)

```
Fahrten pro Woche = Anzahl Schichten          (feste Zeiten)
                  = aufrunden(Stunden / 4)     (flexible Zeiten)
                  davon bei Hybrid die Hälfte (aufgerundet), bei Remote 0

Fahrzeit pro Woche (h) = Fahrten × 2 × einfache Fahrzeit (min) / 60

Effektiver Stundenlohn = Bruttolohn × Stunden / (Stunden + Fahrzeit pro Woche)
```

Beispiele aus den Seed-Daten (Fahrzeiten sind Annahmen):

| Stelle | Brutto | Std./Woche | Fahrten × einfache Fahrzeit | Fahrzeit | Effektiv |
|---|---|---|---|---|---|
| Promoter*in, Weihmann GbR (vor Ort, 2 Schichten) | 16,00 € | 7 | 2 × 18 min | 1,2 h | 13,66 € |
| Werkstudent*in Controlling, Bauer (vor Ort, 3 Schichten) | 15,00 € | 10 | 3 × 12 min | 1,2 h | 13,39 € |
| Aushilfe Lager, Holsten Förster (vor Ort, flexibel) | 14,00 € | 11 | 3 × 35 min | 3,5 h | 10,62 € |
| Werkstudent*in Softwareentwicklung, Weihmann (remote) | 19,50 € | 11 | 0 | 0 h | 19,50 € |

### Qualifikation aus dem Lehrplan (#30, #41)

Jeder Studiengang hat einen Lehrplan: Module pro Semester, und jedes Modul vermittelt Skills (dieselben `Tag`s wie an den Stellen). Für jede Anforderung einer Stelle gilt:

| Einordnung | Bedingung | Anzeige |
|---|---|---|
| gelernt | Skill steht in einem belegten Modul (vorausgewählt: alle Module bis zum aktuellen Semester) oder selbst im Profil | blau, „✓ Python · Programmiertechnik I (1. Sem.)“ bzw. „✓ Englisch · aus deinem Profil“ |
| kommt noch | Skill steht in einem Modul eines späteren Semesters | grau, „SQL · ab 3. Semester“ |
| nicht im Studium | Skill kommt im Lehrplan nicht vor | grau, nur der Name |

In der Liste steht „x von y Anforderungen aus dem Studium“ (gelernt / alle). Stellen ohne Anforderungen zeigen dort nichts. Der Lehrplan kommt zuerst von Hand in den Seed (ITSE am HPI, Semester 1 bis 3) und später per Import aus dem Modulkatalog (#40).

### Sortierung „Passt am besten“ (#42)

Kein gewichteter Punktwert, sondern eine feste Reihenfolge, die man erklären kann:

1. Passung zum Stundenplan: passt oder flexibel vor teilweise vor kollidiert
2. Anteil der Anforderungen, die man laut Lehrplan schon kann
3. effektiver Stundenlohn

Pro Zeile steht, warum die Stelle dort steht, z. B. „Passt in deine Woche · 2 von 2 Anforderungen aus dem Studium · 13,66 € effektiv“.

### Monat und Minijob

Monat ≈ Bruttolohn × Stunden × 4,33, auf ganze Euro gerundet. Bis 603 € (Minijob-Grenze 2026) steht dort „unter der Minijob-Grenze (603 €)“, sonst „über der Minijob-Grenze (603 €)“. Wir zeigen keine Netto-Rechnung. Der Mindestlohn 2026 liegt bei 13,90 €, keine Seed-Stelle darf darunter liegen (#15).

## Ergänzungen am Datenmodell

| Model | Felder | Issue |
|---|---|---|
| `StudentProfile` | User (1:1), Studiengang, Semester, Wohnort, Skills (`Tag`) | #6 |
| Studiengang und Module (Lehrplan) | Studiengang mit Hochschule; Modul mit Semester, Titel, vermittelten Skills (`Tag`); belegte Module am Profil | #30 |
| `LectureSlot` | Profil, Wochentag, Beginn, Ende, Titel (von Hand oder aus `.ics`) | #7, #43 |
| `Shift` | Stelle, Wochentag, Beginn, Ende | #8 |
| `PlannedShift` | Profil, Stelle, Wochentag, Beginn, Ende | #11 |
| `Company.commute_minutes` | einfache Fahrzeit (Annahme im Seed) | #12 |
| `SavedPosting` | Profil, Stelle | #13 |
| `Application` | Profil, Stelle, Zeitpunkt, Status | #14 |

Wochentage als Zahl 0–4 (Mo–Fr), Uhrzeiten als `TimeField`.

## Demo-Daten

Der Seed legt die Demo-Studentin **Mia** an: IT-Systems Engineering, 1. Semester, wohnt in Potsdam, Skills Python, Englisch und Informatik. Ihr Stundenplan:

| Tag | Zeit | Veranstaltung |
|---|---|---|
| Mo | 9:15–12:30 | Mathematik I |
| Mo | 13:30–15:00 | Programmiertechnik I |
| Di | 9:15–10:45 | Digitale Systeme |
| Di | 11:00–12:30 | Modellierung I |
| Mi | 9:15–12:30 | Programmiertechnik I |
| Do | 13:30–17:00 | Übungen Mathe / Digitale Systeme |
| Fr | 9:15–12:30 | Wirtschaftliche Grundlagen |

## Bewusst nicht im Prototyp

Netto-Lohn, Konten für Firmen, Lehrpläne anderer Hochschulen, Noten und bestandene Prüfungen, Drag-and-drop im Kalender, Dark Mode.

## Issues in sinnvoller Reihenfolge

| Nr. | Thema | Baut auf |
|---|---|---|
| #3 | Basis-Template, Kopfzeile, Tokens | – |
| #15 | Seed korrigieren | – |
| #4 | Stellenliste mit Filtern | #3 |
| #5 | Stellendetail, Tab „Details“ | #3 |
| #6 | Login und Studi-Profil | #3 |
| #8 | Schichtzeiten an Stellen | – |
| #12 | Effektiver Stundenlohn | #4, #5, #8 |
| #7 | Stundenplan erfassen | #6 |
| #9 | Passung und Filter | #4, #7, #8 |
| #10 | Tab „In meiner Woche“ | #5, #9 |
| #11 | Flexible Stellen: eigene Schichten | #10 |
| #13 | Stellen merken | #5, #6 |
| #14 | Mit Profil bewerben | #5, #6 |
| #30 | Lehrplan: Module und Skills | #6 |
| #40 | Lehrplan aus dem Modulkatalog einlesen | #30 |
| #41 | Qualifikation pro Stelle | #30, #5 |
| #43 | Stundenplan als ICS-Datei hochladen | #7 |
| #42 | Sortierung „Passt am besten“ | #9, #41, #12 |

Weitere Issues aus der Gruppensitzung (Ort und Karte #20–#22, Uni-Mail bestätigen #31, Bewertungen #32, Eventhub #33, Alerts #34, Onboarding #35 u. a.) stehen in GitHub; sie ändern an diesem Design nichts Grundsätzliches.
