"""Daten für den Tab „In meiner Woche“ (#10): Kalender Mo–Fr, 8–20 Uhr (docs/design.md).

Positionen sind Prozent der Kalenderhöhe (8 Uhr = 0 %, 20 Uhr = 100 %), damit dieselben
Blöcke am Handy (30 px pro Stunde) und am Rechner (48 px pro Stunde) passen. Sie sind
als Text mit Punkt formatiert, weil das deutsche Zahlenformat in CSS nicht funktioniert.
"""

from jobs.models import Weekday

from .fit import shift_collides
from .free_time import DAY_END, DAY_START, to_minutes

DAY_LABELS = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr"}


def _percent(minutes):
    start, end = to_minutes(DAY_START), to_minutes(DAY_END)
    clipped = min(max(minutes, start), end)
    return (clipped - start) / (end - start) * 100


def _block(kind, label, start, end):
    top = _percent(to_minutes(start))
    bottom = _percent(to_minutes(end))
    return {
        "kind": kind,
        "label": label,
        "time": f"{start.hour}:{start:%M}–{end.hour}:{end:%M}",
        "top": f"{top:.4f}",
        "height": f"{bottom - top:.4f}",
    }


def week_view(posting, lectures, shifts=None):
    """{"days": [{"label", "blocks"}], "hours": [{"label", "top"}]} für die Vorlage.

    Vorlesungen sind "lecture", Schichten "shift" oder, wenn sie mit einer Vorlesung
    kollidieren (gleiche Regel und gleicher Puffer wie die Passung), "conflict".
    """
    if shifts is None:
        shifts = list(posting.shifts.all())
    buffer_minutes = posting.one_way_commute_minutes
    days = []
    for weekday in Weekday.values:
        blocks = [
            _block("lecture", lecture.title, lecture.start, lecture.end)
            for lecture in sorted(lectures, key=lambda lecture: lecture.start)
            if lecture.weekday == weekday
        ]
        for shift in sorted(shifts, key=lambda shift: shift.start):
            if shift.weekday != weekday:
                continue
            if shift_collides(shift, lectures, buffer_minutes):
                blocks.append(_block("conflict", "Konflikt", shift.start, shift.end))
            else:
                blocks.append(_block("shift", "Schicht", shift.start, shift.end))
        days.append({"label": DAY_LABELS[weekday], "blocks": blocks})
    hours = [
        {"label": str(hour), "top": f"{_percent(hour * 60):.4f}"}
        for hour in range(DAY_START.hour, DAY_END.hour + 1, 2)
    ]
    return {"days": days, "hours": hours}
