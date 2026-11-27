from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile", verbose_name="Konto"
    )
    study_program = models.CharField("Studiengang", max_length=100, blank=True)  # z. B. "ITSE"
    semester = models.PositiveSmallIntegerField("Semester", null=True, blank=True)
    home_town = models.CharField("Wohnort", max_length=100, blank=True)
    skills = models.ManyToManyField("jobs.Tag", related_name="students", blank=True, verbose_name="Skills")

    class Meta:
        verbose_name = "Studi-Profil"
        verbose_name_plural = "Studi-Profile"

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def summary(self):
        """Kurzzeile für den Profil-Knopf, z. B. „ITSE · 1. Semester“."""
        parts = [self.study_program] if self.study_program else []
        if self.semester:
            parts.append(f"{self.semester}. Semester")
        return " · ".join(parts)
