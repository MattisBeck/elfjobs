"""Schichten vorschlagen beim Bewerben (#141).

Verteilt die Wochenstunden einer flexiblen Stelle auf die freien Zeiten im Stundenplan.
Regeln: höchstens 4 h pro Schicht, halbe Stunden, zwischen 8 und 20 Uhr, vor und nach
einer Vorlesung bleibt die einfache Fahrzeit frei, möglichst auf verschiedene Tage verteilt.
"""

from collections import namedtuple

from jobs.models import Weekday
from timetable.free_time import DAY_END, DAY_START, to_minutes, to_time

MAX_SHIFT_MINUTES = 4 * 60
MIN_SHIFT_MINUTES = 60  # kürzere Lücken sind für eine Schicht nicht der Mühe wert
STEP = 30

Slot = namedtuple("Slot", "weekday start end")


def free_intervals(weekday, lectures, existing, buffer_minutes):
    """Freie Zeiten eines Tages in Minuten als Liste von [von, bis], auf halbe Stunden gerundet."""
    day_start, day_end = to_minutes(DAY_START), to_minutes(DAY_END)
    busy = []
    for lecture in lectures:
        if lecture.weekday == weekday:
            busy.append((to_minutes(lecture.start) - buffer_minutes, to_minutes(lecture.end) + buffer_minutes))
    for shift in existing:
        if shift.weekday == weekday:
            busy.append((to_minutes(shift.start), to_minutes(shift.end)))
    intervals = []
    cursor = day_start
    for start, end in sorted(busy) + [(day_end, day_end)]:
        start = min(start, day_end)
        # Anfang nach oben, Ende nach unten auf die halbe Stunde: so bleibt der Puffer sicher frei.
        low = -(-cursor // STEP) * STEP
        high = start // STEP * STEP
        if high - low >= MIN_SHIFT_MINUTES:
            intervals.append([low, high])
        cursor = max(cursor, end)
    return intervals


def suggest_shifts(posting, lectures, existing, other_shifts=()):
    """Schichten, die die fehlenden Wochenstunden in freie Zeiten legen.

    lectures und existing: Dinge mit weekday, start und end. existing sind schon geplante
    Schichten der Stelle, sie zählen mit und bleiben unberührt. other_shifts sind eigene
    Schichten bei anderen Stellen: Die Zeit ist belegt, zählt aber nicht zu den Stunden dieser Stelle.
    Gibt (neue Schichten als Slot, fehlende Minuten) zurück. Fehlende Minuten sind 0, wenn alles passt.
    """
    lectures, existing = list(lectures), list(existing)
    busy_shifts = existing + list(other_shifts)
    buffer_minutes = posting.one_way_commute_minutes
    assigned = {day: 0 for day in Weekday.values}
    for shift in existing:
        assigned[shift.weekday] += to_minutes(shift.end) - to_minutes(shift.start)
    needed = posting.hours_per_week * 60 - sum(assigned.values())
    intervals = {day: free_intervals(day, lectures, busy_shifts, buffer_minutes) for day in Weekday.values}

    slots = []
    while needed > 0:
        days = [day for day in Weekday.values if intervals[day]]
        if not days:
            break
        # Der Tag mit den wenigsten Stunden zuerst, bei Gleichstand der frühere Wochentag.
        day = min(days, key=lambda d: (assigned[d], d))
        interval = intervals[day][0]
        length = min(MAX_SHIFT_MINUTES, needed, interval[1] - interval[0])
        slots.append(Slot(day, to_time(interval[0]), to_time(interval[0] + length)))
        assigned[day] += length
        needed -= length
        interval[0] += length
        if interval[1] - interval[0] < MIN_SHIFT_MINUTES:
            intervals[day].pop(0)
    slots.sort()
    return slots, max(needed, 0)
