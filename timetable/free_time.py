"""Freie Blöcke im Stundenplan: Lücken von mindestens 2 h zwischen 8 und 20 Uhr (docs/design.md)."""

from dataclasses import dataclass
from datetime import time

from jobs.models import Weekday

DAY_START = time(8, 0)
DAY_END = time(20, 0)
MIN_BLOCK_MINUTES = 2 * 60


def to_minutes(t):
    return t.hour * 60 + t.minute


def to_time(minutes):
    return time(minutes // 60, minutes % 60)


@dataclass
class FreeBlock:
    weekday: int
    start: time
    end: time

    @property
    def hours(self):
        return (to_minutes(self.end) - to_minutes(self.start)) / 60

    def __str__(self):
        return f"{Weekday(self.weekday).label} {self.start:%H:%M}–{self.end:%H:%M}"


def free_blocks(lectures):
    """Freie Blöcke Mo–Fr für eine Liste von Terminen (alles mit weekday, start und end)."""
    lectures = list(lectures)
    day_start, day_end = to_minutes(DAY_START), to_minutes(DAY_END)
    blocks = []
    for weekday in Weekday.values:
        # Termine auf 8–20 Uhr begrenzen und nach Beginn sortieren.
        busy = sorted(
            (max(to_minutes(l.start), day_start), min(to_minutes(l.end), day_end))
            for l in lectures
            if l.weekday == weekday
        )
        cursor = day_start
        for start, end in busy + [(day_end, day_end)]:
            if start - cursor >= MIN_BLOCK_MINUTES:
                blocks.append(FreeBlock(weekday, to_time(cursor), to_time(start)))
            cursor = max(cursor, end)
    return blocks


def free_hours(blocks):
    return sum(block.hours for block in blocks)
