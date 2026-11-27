import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from jobs.models import Tag
from studies.models import Course, StudyProgram

from .models import ProfileSkill, StudentProfile


# Leerzeichen und unsichtbare Zeichen am Rand, z. B. Tab, geschütztes Leerzeichen oder
# Zero-Width-Space aus Copy-Paste (#129).
EMAIL_EDGES = re.compile(r"^[\s\u200b-\u200d\u2060\ufeff]+|[\s\u200b-\u200d\u2060\ufeff]+$")


def normalize_email(value):
    """Mail so, wie wir sie speichern: ohne Zeichen am Rand und kleingeschrieben."""
    return EMAIL_EDGES.sub("", value).lower()


class MailField(forms.EmailField):
    """Mail-Feld für Login und Registrierung: erst normalisieren, dann als Mail prüfen."""

    widget = forms.EmailInput(attrs={"autocomplete": "email"})
    default_error_messages = {"invalid": "Das ist keine gültige Mail-Adresse. Steckt ein Leerzeichen drin?"}

    def to_python(self, value):
        return normalize_email(super().to_python(value))


def is_uni_email(email):
    domain = email.rsplit("@", 1)[-1]
    return any(domain == d or domain.endswith("." + d) for d in settings.UNI_EMAIL_DOMAINS)


def default_courses(program, semester):
    """Module des Studiengangs bis zum aktuellen Semester, z. B. für die Vorauswahl."""
    if program is None or semester is None:
        return Course.objects.none()
    return Course.objects.filter(program=program, semester__lte=semester)


class SignupForm(UserCreationForm):
    """Registrierung nur mit Uni-Mail. Die Mail ist zugleich der Benutzername."""

    email = MailField(label="Uni-Mail", help_text="Zum Start nur mit HPI-Mail, z. B. vorname.nachname@student.hpi.uni-potsdam.de")
    study_program = forms.ModelChoiceField(label="Studiengang", queryset=StudyProgram.objects.all())
    semester = forms.IntegerField(label="Semester", min_value=1, max_value=20)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # UserCreationForm bringt ein eigenes Feld "username" mit, wir nutzen die Mail.
        self.fields.pop("username", None)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not is_uni_email(email):
            raise forms.ValidationError("Bitte registriere dich mit deiner Uni-Mail.")
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Mit dieser Mail gibt es schon ein Konto.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        # Erst aktiv, wenn die Mail bestätigt ist (#31, accounts/views.py confirm_email).
        user.is_active = False
        if commit:
            user.save()
            profile = StudentProfile.objects.create(
                user=user,
                study_program=self.cleaned_data["study_program"],
                semester=self.cleaned_data["semester"],
            )
            # Vorauswahl: alle Module bis zum aktuellen Semester, abwählen geht im Profil.
            profile.courses.set(default_courses(profile.study_program, profile.semester))
        return user


class LoginForm(AuthenticationForm):
    username = MailField(label="Uni-Mail", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}))

    def clean(self):
        """Django lehnt inaktive Konten mit der allgemeinen Fehlermeldung ab. Stimmt das Passwort,
        sagen wir stattdessen, dass die Mail noch bestätigt werden muss (#31)."""
        try:
            return super().clean()
        except ValidationError:
            username = self.cleaned_data.get("username")
            password = self.cleaned_data.get("password")
            user = User.objects.filter(username=username, is_active=False).first()
            if user and password and user.check_password(password):
                raise ValidationError(
                    "Bitte bestätige zuerst deine Uni-Mail. Den Link haben wir dir per Mail geschickt.",
                    code="inactive",
                ) from None
            raise


class NameForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")


class ProfileForm(forms.ModelForm):
    # Nur die selbst eingetragenen Skills (Quelle "profil"). Skills aus dem Lebenslauf (#50)
    # und aus Modulen bleiben beim Speichern unberührt.
    skills = forms.ModelMultipleChoiceField(
        label="Skills", queryset=Tag.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = StudentProfile
        fields = ("study_program", "semester", "home_town", "courses")
        widgets = {"courses": forms.CheckboxSelectMultiple}
        help_texts = {
            "home_town": "Für die Fahrzeit zu den Stellen. Wir suchen den Ort bei OpenStreetMap (Nominatim), "
            "z. B. „Potsdam-Babelsberg“ oder eine Straße.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = self.instance

        if not self.is_bound:
            # Zur Auswahl stehen nur die Module des eigenen Studiengangs.
            self.fields["courses"].queryset = Course.objects.filter(program_id=profile.study_program_id)
            self.initial["skills"] = Tag.objects.filter(
                profile_skills__profile=profile, profile_skills__source=ProfileSkill.Source.PROFILE
            )
            if not profile.courses.exists():
                self.initial["courses"] = default_courses(profile.study_program, profile.semester)

    def clean_courses(self):
        # Wer den Studiengang wechselt, verliert die Module des alten. Beim nächsten Öffnen
        # sind dann die Module des neuen Studiengangs vorausgewählt.
        program = self.cleaned_data.get("study_program")
        return [course for course in self.cleaned_data["courses"] if course.program == program]

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if commit:
            self.save_profile_skills()
        return profile

    def save_profile_skills(self):
        set_profile_skills(self.instance, self.cleaned_data["skills"])


def set_profile_skills(profile, tags):
    """Selbst eingetragene Skills (Quelle "profil") auf genau diese Tags setzen."""
    selected = set(tags)
    ProfileSkill.objects.filter(profile=profile, source=ProfileSkill.Source.PROFILE).exclude(
        tag__in=selected
    ).delete()
    for tag in selected:
        # Steht der Skill schon aus dem Lebenslauf drin, bleibt diese Quelle.
        ProfileSkill.objects.get_or_create(
            profile=profile, tag=tag, defaults={"source": ProfileSkill.Source.PROFILE}
        )


class OnboardingSkillsForm(forms.Form):
    """Schritt 1 im Onboarding (#35): Skills, die nicht schon aus den Modulen kommen."""

    skills = forms.ModelMultipleChoiceField(
        label="Was kannst du außerdem?", queryset=Tag.objects.order_by("name"),
        required=False, widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, course_skills=(), **kwargs):
        super().__init__(*args, **kwargs)
        # Skills aus den Modulen stehen schon oben, sie werden nicht noch einmal angeboten (#106).
        self.fields["skills"].queryset = Tag.objects.exclude(pk__in=course_skills).order_by("name")


CV_MAX_SIZE = 5 * 1024 * 1024  # 5 MB


class CvUploadForm(forms.ModelForm):
    """Eigenen Lebenslauf hochladen (#38): nur PDF, höchstens 5 MB."""

    class Meta:
        model = StudentProfile
        fields = ("cv_file",)
        widgets = {"cv_file": forms.FileInput(attrs={"accept": "application/pdf,.pdf"})}
        error_messages = {"cv_file": {"invalid_extension": "Bitte lade eine PDF-Datei hoch."}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cv_file"].required = True

    def clean_cv_file(self):
        file = self.cleaned_data["cv_file"]
        if file.size > CV_MAX_SIZE:
            raise ValidationError("Der Lebenslauf darf höchstens 5 MB groß sein.")
        # Die Endung allein reicht nicht: Jede PDF-Datei beginnt mit „%PDF-“.
        if file.read(5) != b"%PDF-":
            raise ValidationError("Bitte lade eine PDF-Datei hoch.")
        file.seek(0)
        return file


class CvSampleForm(forms.ModelForm):
    """Auswahl eines Beispiel-Lebenslaufs (#50), bis der echte Upload (#38) da ist."""

    class Meta:
        model = StudentProfile
        fields = ("cv_sample",)
