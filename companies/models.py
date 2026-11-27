from django.conf import settings
from django.db import models

from jobs.models import Company


class CompanyMember(models.Model):
    """Firmenkonto (#66): ein Login gehört zu genau einer Firma und pflegt deren Stellen."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_member", verbose_name="Konto"
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="members", verbose_name="Firma")

    class Meta:
        verbose_name = "Firmenkonto"
        verbose_name_plural = "Firmenkonten"

    def __str__(self):
        return f"{self.user.username} ({self.company.name})"
