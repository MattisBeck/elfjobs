import math
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.deconstruct import deconstructible


# Minijob-Grenze 2026 in Euro pro Monat
MINIJOB_LIMIT = 603

# Firmenlogos (#73): Upload im Admin nur als Rasterbild. Kein SVG, weil darin Skripte stecken können.
# Kein ImageField, damit wir kein Pillow brauchen: Endung und die ersten Bytes werden selbst geprüft.
LOGO_CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
LOGO_MAX_BYTES = 1024 * 1024


def logo_format(header):
    """Bildformat aus den ersten Bytes der Datei (Magic Bytes), sonst None."""
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def validate_logo_file(file):
    """Höchstens 1 MB und der Inhalt muss zur Endung passen (eine umbenannte SVG fällt hier auf)."""
    if file.size > LOGO_MAX_BYTES:
        raise ValidationError("Das Logo darf höchstens 1 MB groß sein.")
    file.seek(0)
    header = file.read(12)
    file.seek(0)
    extension = file.name.rsplit(".", 1)[-1].lower()
    expected = "jpeg" if extension == "jpg" else extension
    if logo_format(header) != expected:
        raise ValidationError("Die Datei ist kein PNG-, JPG- oder WebP-Bild.")

# Rechtsformen zählen nicht für die Initialen: „Holsten Förster AG & Co. OHG“ → „HF“.
LEGAL_FORMS = {"gmbh", "mbh", "ag", "kg", "kgaa", "ohg", "gbr", "ug", "se", "co", "e.v", "ev", "eg", "stiftung"}


def company_initials(name):
    """Höchstens zwei Großbuchstaben für den Logo-Platzhalter.

    Wörter ohne Buchstaben am Anfang (z. B. „&“) und Rechtsformen fallen weg.
    Ein Wort ergibt einen Buchstaben („Bauer“ → „B“), mehrere die ersten zwei („Müller Schmidt“ → „MS“).
    """
    words = [word for word in name.replace("-", " ").split() if word[0].isalpha()]
    without_legal_forms = [word for word in words if word.lower().rstrip(".") not in LEGAL_FORMS]
    words = without_legal_forms or words
    return "".join(word[0].upper() for word in words[:2]) or "?"


@deconstructible
class SocialLinkValidator:
    """Social-Media-Link (#37): nur https und nur die Domain der Plattform, mit oder ohne www."""

    def __init__(self, domain):
        self.domain = domain

    def __call__(self, value):
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or host not in (self.domain, "www." + self.domain):
            raise ValidationError(f"Bitte einen https-Link auf {self.domain} angeben.")

    def __eq__(self, other):
        return isinstance(other, SocialLinkValidator) and self.domain == other.domain


class Company(models.Model):
    name = models.CharField("Name", max_length=200)
    industry = models.CharField("Branche", max_length=100)  # z. B. "Bank", "Tech"
    # Einfache Fahrzeit für Studierende, im Prototyp eine Annahme (keine Routenberechnung).
    commute_minutes = models.PositiveSmallIntegerField("Fahrzeit (min, einfach)", default=0)
    fairs = models.ManyToManyField(
        "Fair", related_name="companies", blank=True, verbose_name="Messen"
    )
    # Logo (#73): ein Upload im Admin hat Vorrang vor einer Datei unter static/ (für Seed-Firmen).
    logo = models.FileField(
        "Logo", upload_to="logos/", blank=True,
        validators=[FileExtensionValidator(list(LOGO_CONTENT_TYPES)), validate_logo_file],
        help_text="PNG, JPG oder WebP, höchstens 1 MB.",
    )
    logo_static = models.CharField(
        "Logo aus static/", max_length=200, blank=True,
        help_text="Pfad unter static/, z. B. logos/weihmann-gbr.svg (SVG nur hier, aus dem Repo). Ein hochgeladenes Logo hat Vorrang.",
    )
    # Social-Media-Profile (#37), im Stellendetail verlinkt.
    instagram_url = models.URLField(
        "Instagram", blank=True, validators=[SocialLinkValidator("instagram.com")]
    )
    linkedin_url = models.URLField(
        "LinkedIn", blank=True, validators=[SocialLinkValidator("linkedin.com")]
    )
    tiktok_url = models.URLField(
        "TikTok", blank=True, validators=[SocialLinkValidator("tiktok.com")]
    )

    class Meta:
        verbose_name = "Firma"
        verbose_name_plural = "Firmen"

    def __str__(self):
        return self.name

    @property
    def logo_url(self):
        """URL des Logos: Upload vor statischer Datei, ohne Logo None (dann zeigt das Template Initialen)."""
        if self.logo:
            # Kein öffentliches /media/: Uploads kommen über eine eigene View (dort liegen auch Lebensläufe).
            return reverse("company_logo", args=[self.pk])
        if self.logo_static:
            return static(self.logo_static)
        return None

    @property
    def initials(self):
        return company_initials(self.name)


class Fair(models.Model):
    name = models.CharField("Name", max_length=200)
    date = models.DateField("Datum")
    location = models.CharField("Ort", max_length=200)
    # „Ich gehe hin“ (#33)
    visitors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="fairs", blank=True, verbose_name="Besucher*innen"
    )

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
    # Ort der Stelle (#20). Remote-Stellen haben keinen. Koordinaten als Decimal mit
    # 6 Nachkommastellen (~10 cm): exakt gespeichert, damit der Seed reproduzierbar bleibt.
    address = models.CharField("Adresse", max_length=200, blank=True)  # Straße, PLZ, Ort
    latitude = models.DecimalField(
        "Breitengrad", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        "Längengrad", max_digits=9, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField("Erstellt am", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Stelle"
        verbose_name_plural = "Stellen"

    def __str__(self):
        return self.title

    @property
    def has_location(self):
        """True, wenn die Stelle Koordinaten hat (für Karte und Anreise)."""
        return self.latitude is not None and self.longitude is not None

    # Effektiver Stundenlohn, Regeln aus docs/design.md. Für feste Stellen
    # vorher prefetch_related("shifts") nutzen, sonst eine Abfrage pro Stelle.

    @property
    def trips_per_week(self):
        """Wie oft man pro Woche hin- und zurückfährt."""
        if self.workplace == self.Workplace.REMOTE:
            return 0
        if self.schedule == self.Schedule.FIXED:
            trips = len(self.shifts.all())
        else:
            trips = math.ceil(self.hours_per_week / 4)
        if self.workplace == self.Workplace.HYBRID:
            trips = math.ceil(trips / 2)
        return trips

    @property
    def one_way_commute_minutes(self):
        """Einfache Fahrzeit in Minuten, remote 0.

        Eingeloggt mit Wohnort setzt jobs/travel.py apply_home_commutes() die Fahrzeit vom
        Wohnort (#53) als home_commute_minutes; sonst gilt die Annahme der Firma.
        """
        if self.workplace == self.Workplace.REMOTE:
            return 0
        home_minutes = getattr(self, "home_commute_minutes", None)
        if home_minutes is not None:
            return home_minutes
        return self.company.commute_minutes

    @property
    def commute_hours_per_week(self):
        return Decimal(self.trips_per_week * 2 * self.one_way_commute_minutes) / 60

    @property
    def effective_wage(self):
        """Bruttolohn pro Stunde, wenn man die Fahrzeit als Arbeitszeit mitzählt."""
        hours = Decimal(self.hours_per_week)
        if hours == 0:
            # Im Admin sind 0 Stunden möglich; ohne Arbeitszeit gibt es nichts zu verteilen.
            return self.hourly_wage
        wage = self.hourly_wage * hours / (hours + self.commute_hours_per_week)
        return wage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def monthly_wage(self):
        """Brutto im Monat (4,33 Wochen), auf ganze Euro."""
        monthly = self.hourly_wage * self.hours_per_week * Decimal("4.33")
        return monthly.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    @property
    def is_minijob(self):
        return self.monthly_wage <= MINIJOB_LIMIT


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Mo"
    TUESDAY = 1, "Di"
    WEDNESDAY = 2, "Mi"
    THURSDAY = 3, "Do"
    FRIDAY = 4, "Fr"


class Shift(models.Model):
    """Eine feste Schicht einer Stelle, jede Woche zur gleichen Zeit."""

    posting = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="shifts", verbose_name="Stelle"
    )
    weekday = models.PositiveSmallIntegerField("Wochentag", choices=Weekday.choices)
    start = models.TimeField("Beginn")
    end = models.TimeField("Ende")

    class Meta:
        ordering = ["weekday", "start"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="shift_ends_after_start"),
        ]
        verbose_name = "Schicht"
        verbose_name_plural = "Schichten"

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start:%H:%M}–{self.end:%H:%M}"

    @property
    def hours(self):
        return (self.end.hour * 60 + self.end.minute - self.start.hour * 60 - self.start.minute) / 60


class TravelTime(models.Model):
    """Gespeicherte Anreisedauer mit ÖPNV zwischen zwei Punkten (#74), siehe jobs/travel.py.

    Koordinaten auf 3 Nachkommastellen gerundet (etwa 100 m), damit nahe Klicks auf
    der Karte denselben Eintrag treffen. Liegt in der Datenbank, überlebt also
    Neustarts und gilt für alle Prozesse.
    """

    start_lat = models.DecimalField("Start Breitengrad", max_digits=6, decimal_places=3)
    start_lon = models.DecimalField("Start Längengrad", max_digits=6, decimal_places=3)
    dest_lat = models.DecimalField("Ziel Breitengrad", max_digits=6, decimal_places=3)
    dest_lon = models.DecimalField("Ziel Längengrad", max_digits=6, decimal_places=3)
    # None heißt: Die API hat geantwortet, aber keine Verbindung gefunden.
    minutes = models.PositiveSmallIntegerField("Minuten", null=True, blank=True)
    fetched_at = models.DateTimeField("Abgefragt am")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["start_lat", "start_lon", "dest_lat", "dest_lon"], name="unique_travel_route"
            ),
        ]
        verbose_name = "Anreisedauer"
        verbose_name_plural = "Anreisedauern"

    def __str__(self):
        return f"{self.start_lat},{self.start_lon} → {self.dest_lat},{self.dest_lon}: {self.minutes} min"


class SavedPosting(models.Model):
    """Gemerkte Stelle einer Studentin (#13), zu finden unter „Gemerkt“."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_postings", verbose_name="Konto"
    )
    posting = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="saved_by", verbose_name="Stelle"
    )
    created_at = models.DateTimeField("Gemerkt am", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "posting"], name="unique_saved_posting"),
        ]
        verbose_name = "Gemerkte Stelle"
        verbose_name_plural = "Gemerkte Stellen"

    def __str__(self):
        return f"{self.user.username}: {self.posting.title}"
