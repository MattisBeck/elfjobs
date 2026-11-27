from django import forms

from .models import LectureSlot


class LectureSlotForm(forms.ModelForm):
    class Meta:
        model = LectureSlot
        fields = ("title", "weekday", "start", "end")
        widgets = {
            "start": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start"), cleaned.get("end")
        if start and end and end <= start:
            self.add_error("end", "Das Ende muss nach dem Beginn liegen.")
        return cleaned


class IcsUploadForm(forms.Form):
    """Stundenplan als Kalenderdatei (#43), z. B. aus dem Uni-Kalender exportiert."""

    datei = forms.FileField(label="Kalenderdatei (.ics)", widget=forms.ClearableFileInput(attrs={"accept": ".ics,text/calendar"}))
