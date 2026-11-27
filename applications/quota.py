"""Freemium (#62): Wie viele Bewerbungen darf ein Profil diese Woche noch senden?

Eine Woche ist die Kalenderwoche Montag 0 Uhr bis Sonntag 24 Uhr in TIME_ZONE (Europe/Berlin).
Es gibt keinen Zähler in der Datenbank: Gezählt werden die Bewerbungen seit Wochenbeginn.
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Application

# Kostenlos: höchstens so viele Bewerbungen pro Kalenderwoche.
WEEKLY_APPLICATION_LIMIT = 3


def week_start(now=None):
    """Montag 0 Uhr der Woche, in der ``now`` liegt (lokale Zeit)."""
    local = timezone.localtime(now or timezone.now())
    monday = local.date() - timedelta(days=local.weekday())
    return timezone.make_aware(datetime.combine(monday, time.min))


def weekly_limit(profile):
    """Kontingent pro Woche. Einladungs-Bonus (#63) und Abo (#64) erweitern später nur diese Funktion."""
    return WEEKLY_APPLICATION_LIMIT


def applications_this_week(profile):
    return Application.objects.filter(profile=profile, applied_at__gte=week_start()).count()


def applications_left(profile):
    return max(weekly_limit(profile) - applications_this_week(profile), 0)
