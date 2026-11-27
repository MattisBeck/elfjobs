from django.db import models

from jobs.models import Weekday


class LectureSlot(models.Model):
    """Ein Termin im Stundenplan (Vorlesung, Übung), jede Woche zur gleichen Zeit."""

    profile = models.ForeignKey(
        "accounts.StudentProfile",
        on_delete=models.CASCADE,
        related_name="lectures",
        verbose_name="Studi-Profil",
    )
    weekday = models.PositiveSmallIntegerField("Wochentag", choices=Weekday.choices)
    start = models.TimeField("Beginn")
    end = models.TimeField("Ende")
    title = models.CharField("Veranstaltung", max_length=100)  # z. B. "Mathematik I"

    class Meta:
        ordering = ["weekday", "start"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="lecture_ends_after_start"),
        ]
        verbose_name = "Stundenplan-Termin"
        verbose_name_plural = "Stundenplan-Termine"

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start:%H:%M}–{self.end:%H:%M} {self.title}"
