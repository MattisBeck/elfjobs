from django.db import models


class StudyProgram(models.Model):
    name = models.CharField("Name", max_length=100)  # z. B. "IT-Systems Engineering"
    abbreviation = models.CharField("Kürzel", max_length=20)  # z. B. "ITSE"
    university = models.CharField("Hochschule", max_length=100)  # z. B. "HPI"
    standard_semesters = models.PositiveSmallIntegerField("Regelstudienzeit (Semester)")

    class Meta:
        ordering = ["university", "name"]
        constraints = [
            models.UniqueConstraint(fields=["university", "abbreviation"], name="unique_program_per_university"),
        ]
        verbose_name = "Studiengang"
        verbose_name_plural = "Studiengänge"

    def __str__(self):
        return f"{self.name} ({self.university})"


class Course(models.Model):
    """Ein Modul aus dem Lehrplan eines Studiengangs, z. B. „Programmiertechnik I“ im 1. Semester."""

    program = models.ForeignKey(
        StudyProgram, on_delete=models.CASCADE, related_name="courses", verbose_name="Studiengang"
    )
    name = models.CharField("Name", max_length=200)
    short_name = models.CharField("Kurzname", max_length=20, blank=True)  # z. B. "PT1"
    semester = models.PositiveSmallIntegerField("Semester")  # laut Lehrplan
    skills = models.ManyToManyField(
        "jobs.Tag", related_name="courses", blank=True, verbose_name="Vermittelte Skills"
    )

    class Meta:
        ordering = ["program", "semester", "name"]
        constraints = [
            models.UniqueConstraint(fields=["program", "name"], name="unique_course_per_program"),
        ]
        verbose_name = "Modul"
        verbose_name_plural = "Module"

    def __str__(self):
        return f"{self.name} ({self.semester}. Sem.)"

    @property
    def label(self):
        """Kurze Bezeichnung für Hinweise wie „aus PT1“."""
        return self.short_name or self.name
