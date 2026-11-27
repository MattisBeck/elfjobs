from django.db import models


class Company(models.Model):
    name = models.CharField("Name", max_length=200)
    industry = models.CharField("Branche", max_length=100)  # z. B. "Bank", "Tech"
    fairs = models.ManyToManyField(
        "Fair", related_name="companies", blank=True, verbose_name="Messen"
    )

    class Meta:
        verbose_name = "Firma"
        verbose_name_plural = "Firmen"

    def __str__(self):
        return self.name


class Fair(models.Model):
    name = models.CharField("Name", max_length=200)
    date = models.DateField("Datum")
    location = models.CharField("Ort", max_length=200)

    class Meta:
        verbose_name = "Messe"
        verbose_name_plural = "Messen"

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField("Name", max_length=50, unique=True)  # Skills, Studiengänge

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name


class JobPosting(models.Model):
    class Kind(models.TextChoices):
        WORKING_STUDENT = "working_student", "Werkstudent"
        SHORT_JOB = "short_job", "Kurzjob"

    class Workplace(models.TextChoices):
        ONSITE = "onsite", "Vor Ort"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"

    class Schedule(models.TextChoices):
        FIXED = "fixed", "Feste Zeiten"
        FLEXIBLE = "flexible", "Flexibel"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="postings",
        verbose_name="Firma",
    )
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beschreibung", blank=True)
    kind = models.CharField("Art", max_length=20, choices=Kind.choices)
    workplace = models.CharField("Arbeitsort", max_length=10, choices=Workplace.choices)
    schedule = models.CharField("Arbeitszeiten", max_length=10, choices=Schedule.choices)
    hourly_wage = models.DecimalField(
        "Stundenlohn (€)", max_digits=5, decimal_places=2
    )
    hours_per_week = models.PositiveSmallIntegerField("Stunden pro Woche")
    tags = models.ManyToManyField(
        Tag, related_name="postings", blank=True, verbose_name="Tags"
    )
    created_at = models.DateTimeField("Erstellt am", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Stelle"
        verbose_name_plural = "Stellen"

    def __str__(self):
        return self.title
