from urllib.parse import urlencode

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import StudentProfile
from studies.qualification import classify, skill_lookup, summary
from timetable.fit import FLEXIBEL, PASST, posting_fit

from .geo import BERLIN_MITTE, haversine_km, parse_start
from .models import JobPosting

# Filter-Chips der Stellenliste: GET-Parameter "filter", mehrere kombinierbar.
FILTER_CHIPS = {
    "werkstudent": "Werkstudent",
    "kurzjob": "Kurzjob",
    "remote": "Remote",
}

# Chip „Passt in meinen Plan“: für Eingeloggte mit Profil standardmäßig an.
# Ausschalten über ?plan=aus (ein eigener Parameter, weil „kein Filter“ sonst
# nicht von „Chip aus“ zu unterscheiden wäre).
PLAN_CHIP_LABEL = "Passt in meinen Plan"


def with_query(path, params):
    """Pfad plus Query-String aus einer Liste von (Name, Wert)-Paaren."""
    query = urlencode(params)
    return f"{path}?{query}" if query else path


def student_skills(request):
    """Skills der eingeloggten Studentin für die Einordnung der Anforderungen, sonst None."""
    if not request.user.is_authenticated:
        return None
    profile = StudentProfile.objects.filter(user=request.user).first()
    return skill_lookup(profile) if profile else None


def filtered_postings(request, skills=None, keep_params=()):
    """Stellen und Filter-Chips für die linke Spalte, gesteuert über ?filter=... und ?q=...

    keep_params sind weitere (Name, Wert)-Paare, die in den Chip-Links erhalten bleiben,
    z. B. der Startpunkt lat/lon auf der Karte.

    Mit skills (aus student_skills) bekommt jede Stelle einen Hinweis wie
    „2 von 3 Anforderungen aus dem Studium“ (posting.skill_hint).
    """
    active = [f for f in request.GET.getlist("filter") if f in FILTER_CHIPS]

    postings = JobPosting.objects.select_related("company").prefetch_related("shifts", "tags")

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

    # Passung: Stundenplan einmal laden, dann pro Stelle rechnen (ohne weitere Abfragen).
    profile = None
    if request.user.is_authenticated:
        profile = StudentProfile.objects.filter(user=request.user).first()
    plan_on = False
    plan_params = []
    if profile:
        lectures = list(profile.lectures.all())
        postings = list(postings)
        for posting in postings:
            posting.fit = posting_fit(posting, lectures)
        plan_on = request.GET.get("plan") != "aus"
        if plan_on:
            postings = [p for p in postings if p.fit.status in (PASST, FLEXIBEL)]
        else:
            plan_params = [("plan", "aus")]

    # Chips bleiben auf der aktuellen Seite: im Stellendetail bleibt die Stelle offen.
    chips = []
    if profile:
        # Chip ist an: Klick schaltet mit ?plan=aus ab; ist er aus: Klick lässt den Parameter weg.
        chips.append({
            "label": PLAN_CHIP_LABEL,
            "active": plan_on,
            "url": with_query(
                request.path,
                [("filter", f) for f in active] + search_params + ([("plan", "aus")] if plan_on else [])
                + list(keep_params),
            ),
        })
    for key, label in FILTER_CHIPS.items():
        toggled = [f for f in active if f != key] if key in active else active + [key]
        chips.append({
            "label": label,
            "active": key in active,
            "url": with_query(
                request.path,
                [("filter", f) for f in toggled] + search_params + plan_params + list(keep_params),
            ),
        })

    filter_params = [("filter", f) for f in active] + search_params + plan_params
    # Sortiert nach effektivem Stundenlohn (#12). Der wird in Python berechnet, nicht in der DB.
    postings = sorted(postings, key=lambda posting: (-posting.effective_wage, posting.title))
    if skills is not None:
        for posting in postings:
            posting.skill_hint = summary(classify(skills, posting.tags.all()))
    return postings, chips, filter_params


def job_list(request):
    postings, chips, filter_params = filtered_postings(request, student_skills(request))
    return render(request, "jobs/job_list.html", {
        "postings": postings,
        "chips": chips,
        "filter_query": urlencode(filter_params),
    })


def job_detail(request, pk):
    posting = get_object_or_404(
        JobPosting.objects.select_related("company").prefetch_related("tags", "shifts"),
        pk=pk,
    )
    skills = student_skills(request)
    postings, chips, filter_params = filtered_postings(request, skills)
    view = "woche" if request.GET.get("ansicht") == "woche" else "details"

    # Passung der geöffneten Stelle für den Punkt am Tab „In meiner Woche“.
    profile = StudentProfile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    if profile:
        posting.fit = posting_fit(posting, profile.lectures.all())

    # "Das bringst du mit": jede Anforderung eingeordnet (gelernt, kommt noch, nicht im Studium).
    # Ohne Login oder Profil nur die Namen.
    requirements = classify(skills or {}, posting.tags.all())

    return render(request, "jobs/job_detail.html", {
        "posting": posting,
        "requirements": requirements,
        "classified": skills is not None,
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


def job_map(request):
    """Karte mit allen Stellen und Liste nach Luftlinie zum Startpunkt (?lat=...&lon=...)."""
    start = parse_start(request.GET.get("lat"), request.GET.get("lon"))
    if start:
        start_params = [("lat", request.GET["lat"]), ("lon", request.GET["lon"])]
    else:
        start, start_params = BERLIN_MITTE, []
    postings, chips, filter_params = filtered_postings(request, student_skills(request), start_params)

    # Stellen mit Ort nach Entfernung, Stellen ohne Ort (remote) in einem eigenen Abschnitt.
    nearby = []
    remote = []
    for posting in postings:
        if posting.has_location:
            posting.distance_km = haversine_km(
                start[0], start[1], float(posting.latitude), float(posting.longitude)
            )
            nearby.append(posting)
        else:
            remote.append(posting)
    nearby.sort(key=lambda posting: (posting.distance_km, posting.title))

    filter_query = urlencode(filter_params)
    # Daten für die Marker, kommen per json_script ins Template (escaped).
    markers = []
    for posting in nearby:
        url = reverse("job_detail", args=[posting.pk])
        markers.append({
            "lat": float(posting.latitude),
            "lon": float(posting.longitude),
            "title": posting.title,
            "company": posting.company.name,
            "wage": f"{posting.effective_wage} €".replace(".", ","),
            "url": f"{url}?{filter_query}" if filter_query else url,
        })

    return render(request, "jobs/job_map.html", {
        "nearby": nearby,
        "remote": remote,
        "chips": chips,
        "filter_query": filter_query,
        "start": {"lat": start[0], "lon": start[1]},
        "has_start": bool(start_params),
        "markers": markers,
    })
