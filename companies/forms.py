from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from jobs.models import Company, JobPosting, Shift

from .models import CompanyMember


class CompanySignupForm(UserCreationForm):
    """Firmenkonto anlegen: legt die Firma gleich mit an. Die Mail ist der Benutzername."""

    email = forms.EmailField(label="Mail")
    company_name = forms.CharField(label="Name der Firma", max_length=200)
    industry = forms.CharField(label="Branche", max_length=100, help_text="z. B. Tech, Handel, Gastronomie")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("username", None)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Mit dieser Mail gibt es schon ein Konto.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
            company = Company.objects.create(
                name=self.cleaned_data["company_name"], industry=self.cleaned_data["industry"]
            )
            CompanyMember.objects.create(user=user, company=company)
        return user


class PostingForm(forms.ModelForm):
    class Meta:
        model = JobPosting
        fields = [
            "title", "kind", "workplace", "address", "hours_per_week", "hourly_wage",
            "schedule", "description", "tags",
        ]
        labels = {"tags": "Geforderte Skills", "hourly_wage": "Bruttolohn pro Stunde (€)"}
        help_texts = {
            "address": "Straße, PLZ, Ort. Bei Remote leer lassen.",
            "schedule": "Bei festen Zeiten unten die Schichten eintragen.",
            "tags": "Mehrere mit Strg/Cmd auswählen.",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}


# Feste Schichten der Stelle, jede Woche gleich. Leere Zeilen werden ignoriert.
ShiftFormSet = inlineformset_factory(
    JobPosting, Shift, fields=["weekday", "start", "end"], extra=3, can_delete=True,
    widgets={
        "weekday": forms.Select(attrs={"aria-label": "Wochentag"}),
        "start": forms.TimeInput(attrs={"type": "time", "aria-label": "Beginn"}),
        "end": forms.TimeInput(attrs={"type": "time", "aria-label": "Ende"}),
    },
)
