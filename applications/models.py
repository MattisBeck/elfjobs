from django.db import models


class Application(models.Model):
    """Bewerbung mit dem Profil (#14): ein Klick, die Daten kommen aus dem Studi-Profil."""

    class Status(models.TextChoices):
        SENT = "gesendet", "Gesendet"

    profile = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="applications", verbose_name="Studi-Profil"
    )
    posting = models.ForeignKey(
        "jobs.JobPosting", on_delete=models.CASCADE, related_name="applications", verbose_name="Stelle"
    )
    applied_at = models.DateTimeField("Beworben am", auto_now_add=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.SENT)

    class Meta:
        verbose_name = "Bewerbung"
        verbose_name_plural = "Bewerbungen"
        ordering = ["-applied_at"]
        constraints = [
            # Auf dieselbe Stelle bewirbt man sich nur einmal.
            models.UniqueConstraint(fields=["profile", "posting"], name="unique_application_per_posting"),
        ]

    def __str__(self):
        return f"{self.profile} → {self.posting.title}"
