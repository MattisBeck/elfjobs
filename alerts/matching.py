"""Welche neuen Stellen passen zu einem Alert? Gleiche Regeln wie die Stellenliste (jobs/views.py).

Der Chip „Passt in meinen Plan“ zählt hier noch nicht mit (#34, „später“).
"""

from django.db.models import Q
from django.http import QueryDict

from jobs.filters import filter_labels, matches, parse_filters
from jobs.models import JobPosting
from jobs.views import FILTER_CHIPS


def alert_label(query):
    """Lesbare Beschreibung, z. B. "Kurzjob · „Python“ · ab 15 € brutto"."""
    get = QueryDict(query)
    parts = [FILTER_CHIPS[f] for f in get.getlist("filter") if f in FILTER_CHIPS]
    q = get.get("q", "").strip()
    if q:
        parts.append(f"„{q}“")
    parts += [label for label, _ in filter_labels(parse_filters(get))]
    return " · ".join(parts) or "Alle Stellen"


def new_postings(alert):
    """Stellen, die nach dem letzten Ansehen angelegt wurden und zu den Filtern passen."""
    get = QueryDict(alert.query)
    postings = (
        JobPosting.objects.filter(created_at__gt=alert.last_seen_at)
        .select_related("company")
        .prefetch_related("shifts")
    )
    active = get.getlist("filter")
    kinds = []
    if "werkstudent" in active:
        kinds.append(JobPosting.Kind.WORKING_STUDENT)
    if "kurzjob" in active:
        kinds.append(JobPosting.Kind.SHORT_JOB)
    if kinds:
        postings = postings.filter(kind__in=kinds)
    if "remote" in active:
        postings = postings.filter(workplace=JobPosting.Workplace.REMOTE)
    q = get.get("q", "").strip()
    if q:
        postings = postings.filter(
            Q(title__icontains=q) | Q(company__name__icontains=q) | Q(tags__name__icontains=q)
        ).distinct()
    filters = parse_filters(get)
    return [posting for posting in postings if matches(posting, filters)]
