"""Konflikte eigener Schichten (#140): mit Vorlesungen und mit anderen Schichten."""

from .fit import colliding_lectures
from .free_time import to_minutes


def shift_conflicts(shifts, lectures):
    """Womit kollidiert jede Schicht? Ergebnis: {shift.pk: [Text, ...]}, nur Schichten mit Konflikt.

    Mit Vorlesungen gilt dieselbe Regel wie bei der Passung (timetable/fit.py): Die Vorlesung wird
    um die einfache Fahrzeit der Stelle verlängert, remote ohne Puffer. Mit einer anderen eigenen
    Schicht zählt nur eine echte Überschneidung, ohne Puffer. Wer genau dann anfängt, wenn die
    andere aufhört, kollidiert nicht. Jede Schicht braucht posting mit company.
    """
    shifts = list(shifts)
    result = {}
    for shift in shifts:
        texts = []
        buffer_minutes = shift.posting.one_way_commute_minutes
        for lecture in colliding_lectures(shift, lectures, buffer_minutes):
            texts.append(f"kollidiert mit {lecture.title}")
        for other in shifts:
            if other.pk == shift.pk or other.weekday != shift.weekday:
                continue
            if to_minutes(shift.start) < to_minutes(other.end) and to_minutes(other.start) < to_minutes(shift.end):
                texts.append(f"überschneidet sich mit {other.posting.title} ({other.posting.company.name})")
        if texts:
            result[shift.pk] = texts
    return result
