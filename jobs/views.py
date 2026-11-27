from urllib.parse import urlencode

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import JobPosting

# Filter-Chips der Stellenliste: GET-Parameter "filter", mehrere kombinierbar.
FILTER_CHIPS = {
    "werkstudent": "Werkstudent",
    "kurzjob": "Kurzjob",
    "remote": "Remote",
}


def with_query(path, params):
    """Pfad plus Query-String aus einer Liste von (Name, Wert)-Paaren."""
    query = urlencode(params)
    return f"{path}?{query}" if query else path


def filtered_postings(request):
    """Stellen und Filter-Chips für die linke Spalte, gesteuert über ?filter=... und ?q=..."""
    active = [f for f in request.GET.getlist("filter") if f in FILTER_CHIPS]

    postings = JobPosting.objects.select_related("company").order_by("-hourly_wage", "title")

    # Werkstudent und Kurzjob zusammen zeigen beides, Remote schränkt zusätzlich ein.
    kinds = []
    if "werkstudent" in active:
        kinds.append(JobPosting.Kind.WORKING_STUDENT)
    if "kurzjob" in active:
        kinds.append(JobPosting.Kind.SHORT_JOB)
    if kinds:
        postings = postings.filter(kind__in=kinds)
    if "remote" in active:
        postings = postings.filter(workplace=JobPosting.Workplace.REMOTE)

    # Suchfeld in der Kopfzeile: Titel, Firma oder Skill (Tag).
    q = request.GET.get("q", "").strip()
    if q:
        postings = postings.filter(
            Q(title__icontains=q) | Q(company__name__icontains=q) | Q(tags__name__icontains=q)
        ).distinct()
    search_params = [("q", q)] if q else []

    # Chips bleiben auf der aktuellen Seite: im Stellendetail bleibt die Stelle offen.
    chips = []
    for key, label in FILTER_CHIPS.items():
        toggled = [f for f in active if f != key] if key in active else active + [key]
        chips.append({
            "label": label,
            "active": key in active,
            "url": with_query(request.path, [("filter", f) for f in toggled] + search_params),
        })

    filter_params = [("filter", f) for f in active] + search_params
    return postings, chips, filter_params


def job_list(request):
    postings, chips, filter_params = filtered_postings(request)
    return render(request, "jobs/job_list.html", {
        "postings": postings,
        "chips": chips,
        "filter_query": urlencode(filter_params),
    })


def job_detail(request, pk):
    posting = get_object_or_404(
        JobPosting.objects.select_related("company").prefetch_related("tags"),
        pk=pk,
    )
    postings, chips, filter_params = filtered_postings(request)
    view = "woche" if request.GET.get("ansicht") == "woche" else "details"
    return render(request, "jobs/job_detail.html", {
        "posting": posting,
        # Nur Messen, die noch kommen.
        "fairs": posting.company.fairs.filter(date__gte=timezone.localdate()).order_by("date"),
        "view": view,
        "details_url": with_query(request.path, filter_params),
        "week_url": with_query(request.path, filter_params + [("ansicht", "woche")]),
        "postings": postings,
        "chips": chips,
        "filter_query": urlencode(filter_params),
        "selected_pk": posting.pk,
    })
