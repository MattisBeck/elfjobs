from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import StudentProfile


def is_uni_email(email):
    domain = email.rsplit("@", 1)[-1]
    return any(domain == d or domain.endswith("." + d) for d in settings.UNI_EMAIL_DOMAINS)


class SignupForm(UserCreationForm):
    """Registrierung nur mit Uni-Mail. Die Mail ist zugleich der Benutzername."""

    email = forms.EmailField(label="Uni-Mail", help_text="Zum Start nur mit HPI-Mail, z. B. vorname.nachname@student.hpi.uni-potsdam.de")
    study_program = forms.CharField(label="Studiengang", max_length=100)
    semester = forms.IntegerField(label="Semester", min_value=1, max_value=20)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # UserCreationForm bringt ein eigenes Feld "username" mit, wir nutzen die Mail.
        self.fields.pop("username", None)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if not is_uni_email(email):
            raise forms.ValidationError("Bitte registriere dich mit deiner Uni-Mail.")
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Mit dieser Mail gibt es schon ein Konto.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
            StudentProfile.objects.create(
                user=user,
                study_program=self.cleaned_data["study_program"],
                semester=self.cleaned_data["semester"],
            )
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Uni-Mail")

    def clean_username(self):
        return self.cleaned_data["username"].lower()


class NameForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ("study_program", "semester", "home_town", "skills")
        widgets = {"skills": forms.CheckboxSelectMultiple}
