"""Verfügbarkeit für Firmen (#67): Wann haben Studierende mit bestimmten Skills Zeit?

Pro Stunden-Slot Mo–Fr, 8–20 Uhr, zählen wir die Studierenden, die
- alle gewählten Skills haben (gleiche Regel wie studies/skills.py: belegte Module und eigene Skills) und
- in dem Slot frei sind (gleiche Regel wie bei der Passung, timetable/fit.py: keine Vorlesung,
  die Vorlesung um die Fahrzeit der Firma als Puffer verlängert).

Gezählt werden nur Studierende mit eingetragenem Stundenplan, sonst wissen wir nicht, wann sie Zeit haben.
Datenschutz: Die Firma sieht nur Anzahlen, und unter MIN_COUNT keine genaue Zahl.
"""

from dataclasses import dataclass
from datetime import time

from accounts.models import StudentProfile
from jobs.models import Weekday
from timetable.fit import shift_collides
from timetable.free_time import DAY_END, DAY_START

# Unter dieser Anzahl zeigen wir keine genaue Zahl, damit niemand erkennbar wird.
MIN_COUNT = 3


@dataclass
class Slot:
    """Eine Stunde an einem Wochentag. Hat weekday, start und end wie eine Schicht."""

    weekday: int
    start: time
    end: time


def hour_starts():
    """Die vollen Stunden von 8 bis 19 Uhr (der letzte Slot endet um 20 Uhr)."""
    return [time(hour, 0) for hour in range(DAY_START.hour, DAY_END.hour)]


def learned_skill_ids(profile):
    """Tag-ids, die das Profil hat: aus belegten Modulen und selbst eingetragen.

    Dieselbe Regel wie skill_sources() in studies/skills.py, aber aus vorgeladenen Daten
    (prefetch_related), damit es keine Abfrage pro Studi gibt.
    """
    ids = {profile_skill.tag_id for profile_skill in profile.profile_skills.all()}
    for course in profile.courses.all():
        ids |= {tag.id for tag in course.skills.all()}
    return ids


def matching_students(tags):
    """Alle Studierenden mit Stundenplan, die alle Tags haben. Ohne Tags: alle mit Stundenplan."""
    profiles = (
        StudentProfile.objects.filter(lectures__isnull=False)
        .distinct()
        .prefetch_related("lectures", "profile_skills", "courses__skills")
    )
    wanted = {tag.id for tag in tags}
    return [profile for profile in profiles if wanted <= learned_skill_ids(profile)]


def label(count):
    """Text für einen Slot, z. B. „12 frei“ oder „weniger als 3 frei“."""
    if count < MIN_COUNT:
        return f"weniger als {MIN_COUNT} frei"
    return f"{count} frei"


def short_label(count):
    """Kurzer Text in der Zelle, z. B. „12“ oder „< 3“."""
    if count < MIN_COUNT:
        return f"< {MIN_COUNT}"
    return str(count)


def level(count, total):
    """Stufe 0–4 für die Farbe: Anteil der passenden Studierenden, die frei sind.

    Unter MIN_COUNT immer 0, damit auch die Farbe keine kleine Zahl verrät.
    """
    if count < MIN_COUNT or total == 0:
        return 0
    # 1 = wenige der Passenden frei, 4 = alle frei.
    return 1 + 3 * count // total


def availability(tags, buffer_minutes):
    """Wochenraster als Liste von Zeilen, eine pro Stunde.

    Jede Zeile: {"start": time(8), "end": time(9), "cells": [Zelle Mo, …, Zelle Fr]}.
    Jede Zelle: {"weekday": "Mo", "count": 12, "label": "12 frei", "short": "12", "level": 0–4}.
    Dazu die Anzahl passender Studierender insgesamt.
    """
    students = matching_students(tags)
    lectures_by_student = [list(student.lectures.all()) for student in students]
    total = len(students)

    rows = []
    for start in hour_starts():
        end = time(start.hour + 1, 0)
        cells = []
        for weekday in Weekday:
            slot = Slot(weekday.value, start, end)
            count = sum(
                not shift_collides(slot, lectures, buffer_minutes) for lectures in lectures_by_student
            )
            cells.append({
                "weekday": weekday.label, "count": count, "label": label(count),
                "short": short_label(count), "level": level(count, total),
            })
        rows.append({"start": start, "end": end, "cells": cells})
    return rows, total

