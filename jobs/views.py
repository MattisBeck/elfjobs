from urllib.parse import urlencode

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import StudentProfile
from studies.qualification import classify, skill_lookup, summary
from timetable.fit import FLEXIBEL, PASST, posting_fit

from .filters import (
    FILTER_FIELDS,
    MAP_FILTER_FIELDS,
    apply_filters,
    commute_minutes,
    filter_labels,
    filter_number_params,
    parse_filters,
    slider_settings,
)
from .geo import BERLIN_MITTE, haversine_km, parse_start
from .models import JobPosting
from .travel import MAX_TRAVEL_REQUESTS, travel_times

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


def filtered_postings(request, skills=None, keep_params=(), fields=FILTER_FIELDS, commute_filter=True):
    """Stellen und Filter-Chips für die linke Spalte, gesteuert über ?filter=..., ?q=...
    und die Suchfilter aus jobs/filters.py (?min_lohn=..., ?max_anreise=... usw.).

    keep_params sind weitere (Name, Wert)-Paare, die in den Chip-Links erhalten bleiben,
    z. B. der Startpunkt lat/lon auf der Karte.

    fields sind die erlaubten Suchfilter; die Karte gibt zusätzlich max_km mit und
    wendet die Entfernung selbst an. Mit commute_filter=False bleibt max_anreise außen vor,
    die Karte prüft sie dann selbst mit den ÖPNV-Minuten.

    Mit skills (aus student_skills) bekommt jede Stelle einen Hinweis wie
    „2 von 3 Anforderungen aus dem Studium“ (posting.skill_hint).

    Mit Stundenplan (eingeloggt mit Profil) bekommt jede Stelle ihre Passung (posting.fit,
    siehe timetable/fit.py). Der Chip „Passt in meinen Plan“ ist dann an und zeigt nur
    passende und flexible Stellen; ?plan=aus schaltet ihn ab und bleibt in allen Links erhalten.

    Gibt (postings, chips, filter_params, filter_form) zurück. filter_params sind alle
    aktiven Filter als (Name, Wert)-Paare für Links, filter_form die Daten für das
    Filter-Formular und die versteckten Felder der Suche in der Kopfzeile.
    """
    active = [f for f in request.GET.getlist("filter") if f in FILTER_CHIPS]
    filters = parse_filters(request.GET, fields)
    number_params = filter_number_params(filters)

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
                + number_params + list(keep_params),
            ),
        })
    for key, label in FILTER_CHIPS.items():
        toggled = [f for f in active if f != key] if key in active else active + [key]
        chips.append({
            "label": label,
            "active": key in active,
            "url": with_query(
                request.path,
                [("filter", f) for f in toggled] + search_params + plan_params + number_params + list(keep_params),
            ),
        })

    filter_params = [("filter", f) for f in active] + search_params + plan_params + number_params

    # Aktive Suchfilter als Chips mit ✕: der Link lässt nur diesen Filter weg.
    for label, names in filter_labels(filters):
        chips.append({
            "label": label,
            "active": True,
            "remove": True,
            "url": with_query(
                request.path,
                [(name, value) for name, value in filter_params + list(keep_params) if name not in names],
            ),
        })

    # Sortiert nach effektivem Stundenlohn (#12). Der wird in Python berechnet, nicht in der DB,
    # deshalb laufen auch die Suchfilter erst hier.
    applied = filters if commute_filter else {k: v for k, v in filters.items() if k != "max_anreise"}
    postings = sorted(
        apply_filters(postings, applied), key=lambda posting: (-posting.effective_wage, posting.title)
    )
    if skills is not None:
        for posting in postings:
            posting.skill_hint = summary(classify(skills, posting.tags.all()))

    # Formular „Filter“: Schieberegler plus versteckt alles andere, damit nichts verloren geht.
    # Die Suche in der Kopfzeile behält alles außer q (das ist ihr eigenes Feld).
    other_params = [("filter", f) for f in active] + plan_params + list(keep_params)
    filter_form = {
        "action": request.path,
        "sliders": slider_settings(filters),
        "hidden": other_params + search_params,
        "search_hidden": other_params + number_params,
        "show_km": "max_km" in fields,
        "open": bool(filters),
    }
    return postings, chips, filter_params, filter_form


def job_list(request):
    postings, chips, filter_params, filter_form = filtered_postings(request, student_skills(request))
    return render(request, "jobs/job_list.html", {
        "postings": postings,
        "chips": chips,
        "filter_form": filter_form,
        "filter_query": urlencode(filter_params),
    })


def job_detail(request, pk):
    posting = get_object_or_404(
        JobPosting.objects.select_related("company").prefetch_related("tags", "shifts"),
        pk=pk,
    )
    skills = student_skills(request)
    view = "woche" if request.GET.get("ansicht") == "woche" else "details"
    # Die Wochenansicht bleibt über Chips, Filterformular und Suche erhalten.
    view_params = [("ansicht", "woche")] if view == "woche" else []
    postings, chips, filter_params, filter_form = filtered_postings(request, skills, view_params)

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
        "filter_form": filter_form,
        "filter_query": urlencode(filter_params),
        "selected_pk": posting.pk,
    })


def job_map(request):
    """Karte mit allen Stellen und Liste zum Startpunkt (?lat=...&lon=...).

    Sortiert nach Luftlinie, mit ?sortierung=anreise nach Anreisedauer mit ÖPNV (#22).
    """
    start = parse_start(request.GET.get("lat"), request.GET.get("lon"))
    if start:
        start_params = [("lat", request.GET["lat"]), ("lon", request.GET["lon"])]
    else:
        start, start_params = BERLIN_MITTE, []
    by_travel = request.GET.get("sortierung") == "anreise"
    sort_params = [("sortierung", "anreise")] if by_travel else []
    # Bei Sortierung nach Anreisedauer prüft die Karte max_anreise selbst (unten, mit ÖPNV-Minuten).
    postings, chips, filter_params, filter_form = filtered_postings(
        request, student_skills(request), start_params + sort_params, MAP_FILTER_FIELDS,
        commute_filter=not by_travel,
    )
    filters = parse_filters(request.GET, MAP_FILTER_FIELDS)
    max_km = filters.get("max_km")

    # Stellen mit Ort nach Entfernung, Stellen ohne Ort (remote) in einem eigenen Abschnitt.
    nearby = []
    remote = []
    for posting in postings:
        if posting.has_location:
            posting.distance_km = haversine_km(
                start[0], start[1], float(posting.latitude), float(posting.longitude)
            )
            posting.travel_minutes = None
            # Maximale Entfernung (Luftlinie). Remote-Stellen bleiben im eigenen Abschnitt.
            if max_km is None or posting.distance_km <= max_km:
                nearby.append(posting)
        else:
            remote.append(posting)
    nearby.sort(key=lambda posting: (posting.distance_km, posting.title))

    # Anreisedauer nur, wenn gewählt: die API fragt nur die nächsten Stellen nach Luftlinie.
    # Stellen mit Minuten zuerst (nach Minuten), dann alle übrigen nach Luftlinie.
    travel_hint = ""
    if by_travel:
        times = travel_times(start, nearby)
        for posting in nearby:
            posting.travel_minutes = times.get(posting.id)
        nearby.sort(key=lambda posting: (
            posting.travel_minutes is None,
            posting.travel_minutes or 0,
            posting.distance_km,
            posting.title,
        ))
        asked = min(len(nearby), MAX_TRAVEL_REQUESTS)
        if asked and not times:
            travel_hint = "Anreisedauer gerade nicht verfügbar, sortiert nach Luftlinie."
        elif len(times) < asked:
            travel_hint = "Anreisedauer nicht für alle Stellen verfügbar, die übrigen nach Luftlinie."

        # Maximale Anreise: ÖPNV-Minuten, wo es sie gibt, sonst die Fahrzeit der Firma.
        if "max_anreise" in filters:
            nearby = [
                posting for posting in nearby
                if (commute_minutes(posting) if posting.travel_minutes is None else posting.travel_minutes)
                <= filters["max_anreise"]
            ]

    # Umschalter für die Sortierung: Filter, Suche und Startpunkt bleiben erhalten.
    sort_links = [
        {"label": "Entfernung", "active": not by_travel,
         "url": with_query(request.path, filter_params + start_params)},
        {"label": "Anreisedauer", "active": by_travel,
         "url": with_query(request.path, filter_params + start_params + [("sortierung", "anreise")])},
    ]

    filter_query = urlencode(filter_params)
    # Daten für die Marker, kommen per json_script ins Template (escaped).
    markers = []
    for posting in nearby:
        url = reverse("job_detail", args=[posting.pk])
        minutes = posting.travel_minutes
        markers.append({
            "lat": float(posting.latitude),
            "lon": float(posting.longitude),
            "title": posting.title,
            "company": posting.company.name,
            "wage": f"{posting.effective_wage} €".replace(".", ","),
            "travel": f"ca. {minutes} min mit ÖPNV" if minutes is not None else "",
            "url": f"{url}?{filter_query}" if filter_query else url,
        })

    return render(request, "jobs/job_map.html", {
        "nearby": nearby,
        "remote": remote,
        "chips": chips,
        "filter_form": filter_form,
        "sort_links": sort_links,
        "by_travel": by_travel,
        "travel_hint": travel_hint,
        "max_travel_requests": MAX_TRAVEL_REQUESTS,
        "filter_query": filter_query,
        "start": {"lat": start[0], "lon": start[1]},
        "has_start": bool(start_params),
        "markers": markers,
    })
