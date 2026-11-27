"""Stundenplan aus einer ICS-Datei lesen (#43), wie sie Uni-Kalender exportieren.

Übernommen werden wöchentlich wiederkehrende Termine Mo–Fr. Einzeltermine (z. B. Klausuren),
ganztägige Termine und Wochenenden werden übersprungen und gezählt.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from icalendar import Calendar

# RRULE BYDAY → Weekday (Mo = 0). Samstag und Sonntag fehlen absichtlich.
BYDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4}


class IcsError(ValueError):
    """Die Datei lässt sich nicht lesen. Die Meldung ist für Studierende gedacht."""


def _local(value):
    """datetime in Ortszeit (TIME_ZONE), ohne Zeitzone gilt es schon als Ortszeit."""
    if value.tzinfo is None:
        return value
    return value.astimezone(ZoneInfo(settings.TIME_ZONE))


def _weekdays(event, start):
    """Wochentage eines wöchentlichen Termins, z. B. [1, 3] für BYDAY=TU,TH; Wochenende fällt weg."""
    days = event["RRULE"].get("BYDAY") or []
    if not days:
        return [start.weekday()] if start.weekday() < 5 else []
    # BYDAY kann ein Präfix haben („1MO“); bei wöchentlichen Terminen zählt nur der Tag.
    return sorted({BYDAY[day[-2:]] for day in days if day[-2:] in BYDAY})


def parse_ics(data):
    """Liest eine ICS-Datei (bytes). Gibt (Termine, übersprungen) zurück.

    Termine sind dicts mit weekday, start, end, title, sortiert nach Wochentag und Beginn.
    Wirft IcsError, wenn die Datei kein Kalender ist.
    """
    try:
        calendar = Calendar.from_ical(data)
    except (ValueError, IndexError, KeyError) as error:
        raise IcsError("Das ist keine Kalenderdatei (.ics), die wir lesen können.") from error
    if calendar.name != "VCALENDAR":
        raise IcsError("Das ist keine Kalenderdatei (.ics), die wir lesen können.")

    slots = []
    skipped = 0
    for event in calendar.walk("VEVENT"):
        # Geänderte Einzeltermine einer Serie (RECURRENCE-ID) gehören zur Serie, die schon zählt.
        if event.get("RECURRENCE-ID"):
            continue
        try:
            event_slots = _slots_of(event)
        except (ValueError, AttributeError, TypeError, KeyError):
            # Kaputte Angaben in einem Termin (z. B. "DTSTART:kaputt"): Termin überspringen.
            event_slots = []
        if not event_slots:
            skipped += 1
        for slot in event_slots:
            if slot not in slots:
                slots.append(slot)
    slots.sort(key=lambda slot: (slot["weekday"], slot["start"], slot["title"]))
    return slots, skipped


def _slots_of(event):
    """Termine eines wöchentlichen VEVENT, [] wenn er nicht passt (Einzeltermin, ganztägig, Wochenende)."""
    start = event.get("DTSTART")
    rule = event.get("RRULE")
    if start is None or not isinstance(start.dt, datetime) or not rule or rule.get("FREQ") != ["WEEKLY"]:
        return []
    start_dt = _local(start.dt)
    if event.get("DTEND") is not None:
        if not isinstance(event["DTEND"].dt, datetime):
            return []
        end_dt = _local(event["DTEND"].dt)
    elif event.get("DURATION") is not None:
        end_dt = start_dt + event["DURATION"].dt
    else:
        return []
    weekdays = _weekdays(event, start_dt)
    if not weekdays or end_dt.date() != start_dt.date() or end_dt <= start_dt:
        return []
    title = str(event.get("SUMMARY", "")).strip()[:100] or "Termin"
    return [{"weekday": weekday, "start": start_dt.time(), "end": end_dt.time(), "title": title} for weekday in weekdays]
