from django import forms

from jobs.models import Weekday
from timetable.planning import PlannedShiftForm


class ApplyShiftForm(PlannedShiftForm):
    """Schicht von Hand hinzufügen (#141): wie im Tab „In meiner Woche“, aber mit sichtbarem Wochentag."""

    weekday = forms.TypedChoiceField(label="Tag", choices=Weekday.choices, coerce=int)
