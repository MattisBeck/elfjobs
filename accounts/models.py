from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    class CvSample(models.TextChoices):
        """Beispiel-Lebensläufe aus accounts/sample_cvs/ (#50). Der echte Upload kommt mit #38."""

        MIA = "mia-itse", "Mia Sommer · IT-Systems Engineering"
        JULIA = "julia-politik", "Julia Brandt · Politikwissenschaft"
        JUSTUS = "justus-bwl", "Justus Albrecht · BWL"
        PAULA = "paula-psychologie", "Paula Wendt · Psychologie"
        JONAS = "jonas-wirtschaftsinformatik", "Jonas Petersen · Wirtschaftsinformatik"
        SCAN = "scan-ohne-text", "Eingescannt, ohne Text"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile", verbose_name="Konto"
    )
    study_program = models.ForeignKey(
        "studies.StudyProgram",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
        verbose_name="Studiengang",
    )
    semester = models.PositiveSmallIntegerField("Semester", null=True, blank=True)
    home_town = models.CharField("Wohnort", max_length=100, blank=True)
    # Selbst eingetragene Skills mit Herkunft (siehe ProfileSkill).
    # Skills aus Modulen werden nicht gespeichert, sondern aus courses abgeleitet (studies/skills.py).
    skills = models.ManyToManyField(
        "jobs.Tag", through="ProfileSkill", related_name="students", blank=True, verbose_name="Skills"
    )
    courses = models.ManyToManyField(
        "studies.Course", related_name="students", blank=True, verbose_name="Belegte Module"
    )
    cv_sample = models.CharField("Beispiel-Lebenslauf", max_length=50, choices=CvSample.choices, blank=True)

    class Meta:
        verbose_name = "Studi-Profil"
        verbose_name_plural = "Studi-Profile"

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def summary(self):
        """Kurzzeile für den Profil-Knopf, z. B. „ITSE · 1. Semester“."""
        parts = [self.study_program.abbreviation] if self.study_program else []
        if self.semester:
            parts.append(f"{self.semester}. Semester")
        return " · ".join(parts)


class ProfileSkill(models.Model):
    """Ein Skill, den die Studentin selbst angegeben oder aus dem Lebenslauf übernommen hat."""

    class Source(models.TextChoices):
        PROFILE = "profil", "aus deinem Profil"
        CV = "lebenslauf", "aus deinem Lebenslauf"  # bestätigte Vorschläge, siehe accounts/cv.py

    profile = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="profile_skills", verbose_name="Studi-Profil"
    )
    tag = models.ForeignKey(
        "jobs.Tag", on_delete=models.CASCADE, related_name="profile_skills", verbose_name="Skill"
    )
    source = models.CharField("Quelle", max_length=20, choices=Source.choices, default=Source.PROFILE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile", "tag"], name="unique_skill_per_profile"),
        ]
        verbose_name = "Skill im Profil"
        verbose_name_plural = "Skills im Profil"

    def __str__(self):
        return f"{self.tag} ({self.get_source_display()})"
