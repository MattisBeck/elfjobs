"""Passung einer Stelle zum Stundenplan (Regeln: docs/design.md, Abschnitt „Passung“)."""

from dataclasses import dataclass

from jobs.models import JobPosting

from .free_time import to_minutes

PASST = "passt"
TEILWEISE = "teilweise"
KOLLIDIERT = "kollidiert"
FLEXIBEL = "flexibel"


@dataclass
class Fit:
    status: str
    colliding: int  # Schichten, die mit einer Vorlesung kollidieren
    total: int  # Schichten der Stelle insgesamt
    text: str


def colliding_lectures(shift, lectures, buffer_minutes):
    """Alle Vorlesungen desselben Tages, die die Schicht überschneiden (Vorlesung um den Puffer verlängert).

    Wer genau dann anfängt, wenn die verlängerte Vorlesung endet (oder genau dann
    aufhört, wenn sie beginnt), kollidiert nicht: dafür „<“ statt „<=“.
    """
    start, end = to_minutes(shift.start), to_minutes(shift.end)
    found = []
    for lecture in lectures:
        if lecture.weekday != shift.weekday:
            continue
        lecture_start = to_minutes(lecture.start) - buffer_minutes
        lecture_end = to_minutes(lecture.end) + buffer_minutes
        if start < lecture_end and lecture_start < end:
            found.append(lecture)
    return found


def shift_collides(shift, lectures, buffer_minutes):
    """Überschneidet die Schicht eine Vorlesung desselben Tages (mit Puffer)?"""
    return bool(colliding_lectures(shift, lectures, buffer_minutes))


def posting_fit(posting, lectures):
    """Passung einer Stelle zu einer Liste von Terminen (alles mit weekday, start und end).

    Puffer vor und nach der Vorlesung ist die einfache Fahrzeit der Firma (#12, docs/design.md),
    damit man zur Arbeit und zurück kommt. Remote-Stellen haben keinen Weg und keinen Puffer,
    Hybrid hat einen Weg und bekommt ihn. Für viele Stellen vorher select_related("company").
    """
    shifts = list(posting.shifts.all())
    if posting.schedule == JobPosting.Schedule.FLEXIBLE or not shifts:
        return Fit(FLEXIBEL, 0, len(shifts), "Flexible Zeiten, du wählst die Schichten")

    # Puffer = einfache Fahrzeit: vom Wohnort, wenn bekannt (#53), sonst Annahme der Firma; remote 0.
    buffer_minutes = posting.one_way_commute_minutes
    total = len(shifts)
    colliding = sum(shift_collides(shift, lectures, buffer_minutes) for shift in shifts)

    if colliding == 0:
        return Fit(PASST, 0, total, "Passt in deine Woche")
    if colliding == total:
        return Fit(KOLLIDIERT, colliding, total, "Kollidiert mit Vorlesungen")
    verb = "kollidiert" if colliding == 1 else "kollidieren"
    return Fit(TEILWEISE, colliding, total, f"{colliding} von {total} Schichten {verb}")
