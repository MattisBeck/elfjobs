"""Eigene Schichten bei flexiblen Stellen (#11, docs/design.md).

Studierende legen ihre Schichten selbst in die freien Blöcke ihres Stundenplans.
Frei ist, was nach Vorlesungen und schon geplanten Schichten der Stelle übrig bleibt
(dieselbe Regel wie auf der Stundenplan-Seite: Lücken ab 2 h zwischen 8 und 20 Uhr).
"""

from django import forms

from jobs.models import Weekday

from .free_time import free_blocks, to_minutes, to_time

# Vorschlag beim Antippen eines freien Blocks: bis zu 4 h ab Blockbeginn (wie im Design-Canvas).
SUGGESTED_MINUTES = 4 * 60


def planned_hours(planned):
    return sum(to_minutes(shift.end) - to_minutes(shift.start) for shift in planned) / 60


def open_blocks(lectures, planned):
    """Freie Blöcke, in denen noch keine eigene Schicht liegt."""
    return free_blocks(list(lectures) + list(planned))


def block_key(block):
    """Kennung eines freien Blocks im Link, z. B. "1-0800" für Di ab 8 Uhr."""
    return f"{block.weekday}-{block.start:%H%M}"


class PlannedShiftForm(forms.Form):
    weekday = forms.TypedChoiceField(choices=Weekday.choices, coerce=int, widget=forms.HiddenInput)
    start = forms.TimeField(label="Beginn", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    end = forms.TimeField(label="Ende", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))

    def __init__(self, *args, posting, lectures, planned, **kwargs):
        super().__init__(*args, **kwargs)
        self.posting = posting
        self.lectures = lectures
        self.planned = planned

    def clean(self):
        cleaned = super().clean()
        weekday, start, end = cleaned.get("weekday"), cleaned.get("start"), cleaned.get("end")
        if weekday is None or not start or not end:
            return cleaned
        if end <= start:
            raise forms.ValidationError("Das Ende muss nach dem Beginn liegen.")
        if not any(
            block.weekday == weekday and block.start <= start and end <= block.end
            for block in open_blocks(self.lectures, self.planned)
        ):
            raise forms.ValidationError("Die Schicht muss in einem freien Block liegen.")
        hours = planned_hours(self.planned) + (to_minutes(end) - to_minutes(start)) / 60
        if hours > self.posting.hours_per_week:
            raise forms.ValidationError(f"Damit wären mehr als {self.posting.hours_per_week} h verplant.")
        return cleaned


def planning_context(posting, lectures, planned, chosen_key):
    """Daten für den Hinweis unter dem Kalender und das Formular zum gewählten freien Block."""
    hours = planned_hours(planned)
    open_minutes = round((posting.hours_per_week - hours) * 60)
    block = next((b for b in open_blocks(lectures, planned) if block_key(b) == chosen_key), None)
    form = None
    if block and open_minutes > 0:
        start = to_minutes(block.start)
        end = min(start + SUGGESTED_MINUTES, to_minutes(block.end), start + open_minutes)
        form = PlannedShiftForm(
            posting=posting, lectures=lectures, planned=planned,
            initial={"weekday": block.weekday, "start": block.start, "end": to_time(end)},
        )
    return {"hours": hours, "block": block, "form": form}


def shift_label(weekday, start, end):
    return f"{Weekday(weekday).label} {start:%H:%M}–{end:%H:%M}"

