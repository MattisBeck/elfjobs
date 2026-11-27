"""Passung einer Stelle zum Stundenplan (Regeln: docs/design.md, Abschnitt „Passung“)."""

from dataclasses import dataclass

from jobs.models import JobPosting

from .free_time import to_minutes

# Pufferzeit vor und nach jeder Vorlesung, damit man zur Arbeit kommt.
# Wird durch die Fahrzeit der Firma aus #12 ersetzt.
COMMUTE_BUFFER_MINUTES = 30

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


def shift_collides(shift, lectures, buffer_minutes):
    """Überschneidet die Schicht eine Vorlesung desselben Tages (Vorlesung um den Puffer verlängert)?

    Wer genau dann anfängt, wenn die verlängerte Vorlesung endet (oder genau dann
    aufhört, wenn sie beginnt), kollidiert nicht: dafür „<“ statt „<=“.
    """
    start, end = to_minutes(shift.start), to_minutes(shift.end)
    for lecture in lectures:
        if lecture.weekday != shift.weekday:
            continue
        lecture_start = to_minutes(lecture.start) - buffer_minutes
        lecture_end = to_minutes(lecture.end) + buffer_minutes
        if start < lecture_end and lecture_start < end:
            return True
    return False


def posting_fit(posting, lectures):
    """Passung einer Stelle zu einer Liste von Terminen (alles mit weekday, start und end).

    Der Puffer gilt vor und nach der Vorlesung, außer bei Remote-Stellen (kein Weg).
    Hybrid hat Weg, bekommt also den Puffer.
    """
    shifts = list(posting.shifts.all())
    if posting.schedule == JobPosting.Schedule.FLEXIBLE or not shifts:
        return Fit(FLEXIBEL, 0, len(shifts), "Flexible Zeiten, du wählst die Schichten")

    buffer_minutes = 0 if posting.workplace == JobPosting.Workplace.REMOTE else COMMUTE_BUFFER_MINUTES
    total = len(shifts)
    colliding = sum(shift_collides(shift, lectures, buffer_minutes) for shift in shifts)

    if colliding == 0:
        return Fit(PASST, 0, total, "Passt in deine Woche")
    if colliding == total:
        return Fit(KOLLIDIERT, colliding, total, "Kollidiert mit Vorlesungen")
    verb = "kollidiert" if colliding == 1 else "kollidieren"
    return Fit(TEILWEISE, colliding, total, f"{colliding} von {total} Schichten {verb}")
