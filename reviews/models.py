from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """Bewertung einer Firma durch eine Studentin (#32): 1–5 Sterne und ein kurzer Text.

    Nur wer sich bei der Firma beworben hat, darf bewerten (geprüft in views.py).
    Pro Person und Firma gibt es eine Bewertung, erneutes Absenden ändert sie.
    """

    profile = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="reviews", verbose_name="Studi-Profil"
    )
    company = models.ForeignKey(
        "jobs.Company", on_delete=models.CASCADE, related_name="reviews", verbose_name="Firma"
    )
    stars = models.PositiveSmallIntegerField(
        "Sterne", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    text = models.CharField("Text", max_length=500)
    created_at = models.DateTimeField("Erstellt am", auto_now_add=True)
    updated_at = models.DateTimeField("Geändert am", auto_now=True)

    class Meta:
        verbose_name = "Bewertung"
        verbose_name_plural = "Bewertungen"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "company"], name="unique_review_per_company"),
            models.CheckConstraint(condition=models.Q(stars__gte=1, stars__lte=5), name="review_stars_1_to_5"),
        ]

    def __str__(self):
        return f"{self.company} · {self.stars} Sterne"
