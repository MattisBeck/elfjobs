from django.conf import settings
from django.db import models
from django.utils import timezone


class JobAlert(models.Model):
    """Gespeicherte Suche (#34). Neue passende Stellen erscheinen als Hinweis in der Kopfzeile."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_alerts", verbose_name="Konto"
    )
    # Filter wie in den Links der Stellenliste, z. B. "filter=kurzjob&q=Python&min_lohn=15".
    query = models.CharField("Filter", max_length=500, blank=True)
    label = models.CharField("Beschreibung", max_length=300)  # z. B. "Kurzjob · „Python“"
    created_at = models.DateTimeField("Erstellt am", auto_now_add=True)
    # Stellen, die danach angelegt wurden, zählen als neu.
    last_seen_at = models.DateTimeField("Zuletzt angesehen", default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Job-Alert"
        verbose_name_plural = "Job-Alerts"

    def __str__(self):
        return self.label
