from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import StudentProfile
from studies.qualification import LEARNED, classify, skill_lookup, summary, verdict
from timetable.fit import FLEXIBEL, KOLLIDIERT, PASST, TEILWEISE, posting_fit
from timetable.week import week_view

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
from .models import Company, Fair, JobPosting, SavedPosting
from .travel import MAX_TRAVEL_REQUESTS, apply_home_commutes, cached_travel_times, fetch_travel_times

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


# Sortierung „Passt am besten“ (#42): erst Stundenplan, dann Lehrplan, dann Lohn.
FIT_RANK = {PASST: 0, FLEXIBEL: 0, TEILWEISE: 1, KOLLIDIERT: 2}


def best_fit_key(posting):
    """Sortierschlüssel für „Passt am besten“, ohne gewichtete Formel, damit man es nachvollziehen kann:

    1. Passung zum Stundenplan (passt oder flexibel vor teilweise vor kollidiert),
    2. Anteil der Anforderungen, die man laut Lehrplan schon kann (keine Anforderungen = alles),
    3. effektiver Stundenlohn, bei Gleichstand der Titel.
    """
    fit = getattr(posting, "fit", None)
    fit_rank = FIT_RANK[fit.status] if fit else 0
    requirements = posting.requirements
    learned = sum(1 for r in requirements if r["status"] == LEARNED)
    share = learned / len(requirements) if requirements else 1
    return (fit_rank, -share, -posting.effective_wage, posting.title)


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

    # Reihenfolge: Mit Lehrplan (skills) ist „Passt am besten“ Standard, ?reihenfolge=lohn wählt den Lohn.
    by_wage = skills is None or request.GET.get("reihenfolge") == "lohn"
    order_params = [("reihenfolge", "lohn")] if skills is not None and by_wage else []

    # Passung: Stundenplan einmal laden, dann pro Stelle rechnen (ohne weitere Abfragen).
    profile = None
    if request.user.is_authenticated:
        profile = StudentProfile.objects.filter(user=request.user).first()
    plan_on = False
    plan_params = []
    if profile:
        lectures = list(profile.lectures.all())
        postings = list(postings)
        # Fahrzeit vom Wohnort (#53) vor Passung, Lohn und Filtern setzen.
        apply_home_commutes(profile, postings)
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
                + order_params + number_params + list(keep_params),
            ),
        })
    for key, label in FILTER_CHIPS.items():
        toggled = [f for f in active if f != key] if key in active else active + [key]
        chips.append({
            "label": label,
            "active": key in active,
            "url": with_query(
                request.path,
                [("filter", f) for f in toggled] + search_params + plan_params + order_params
                + number_params + list(keep_params),
            ),
        })

    filter_params = [("filter", f) for f in active] + search_params + plan_params + order_params + number_params

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

    # Sortiert nach „Passt am besten“ (#42) oder effektivem Stundenlohn (#12). Beides wird in Python
    # berechnet, nicht in der DB, deshalb laufen auch die Suchfilter erst hier.
    applied = filters if commute_filter else {k: v for k, v in filters.items() if k != "max_anreise"}
    postings = apply_filters(postings, applied)
    if skills is not None:
        for posting in postings:
            posting.requirements = classify(skills, posting.tags.all())
            posting.skill_hint = summary(posting.requirements)
            posting.verdict = verdict(posting.requirements)
    if by_wage:
        postings = sorted(postings, key=lambda posting: (-posting.effective_wage, posting.title))
    else:
        postings = sorted(postings, key=best_fit_key)

    # Umschalter der Reihenfolge, nur mit Lehrplan. Alle anderen Parameter bleiben erhalten.
    sort_links = []
    if skills is not None:
        base = [(name, value) for name, value in filter_params if name != "reihenfolge"]
        sort_links = [
            {"label": "Passt am besten", "active": not by_wage, "url": with_query(request.path, base)},
            {"label": "Effektiver Lohn", "active": by_wage,
             "url": with_query(request.path, base + [("reihenfolge", "lohn")])},
        ]

    # Formular „Filter“: Schieberegler plus versteckt alles andere, damit nichts verloren geht.
    # Die Suche in der Kopfzeile behält alles außer q (das ist ihr eigenes Feld).
    other_params = [("filter", f) for f in active] + plan_params + order_params + list(keep_params)
    filter_form = {
        "action": request.path,
        "sliders": slider_settings(filters),
        "hidden": other_params + search_params,
        "search_hidden": other_params + number_params,
        "show_km": "max_km" in fields,
        "sort_links": sort_links,
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
        apply_home_commutes(profile, [posting])
        posting.fit = posting_fit(posting, profile.lectures.all())

    # "Das bringst du mit": jede Anforderung eingeordnet (gelernt, kommt noch, nicht im Studium).
    # Ohne Login oder Profil nur die Namen.
    requirements = classify(skills or {}, posting.tags.all())

    # Tab „In meiner Woche“ (#10): ohne Profil nur die Schichten.
    week = None
    if view == "woche":
        week = week_view(posting, list(profile.lectures.all()) if profile else [])

    return render(request, "jobs/job_detail.html", {
        "posting": posting,
        "week": week,
        "has_profile": profile is not None,
        "requirements": requirements,
        # „✓ Du bist qualifiziert“ (#86), nur mit Profil.
        "verdict": verdict(requirements) if skills is not None else None,
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
        # Merken (#13): nur Studierende, Firmenkonten sehen keinen Knopf.
        "can_save": is_student(request.user),
        "is_saved": is_student(request.user) and posting.saved_by.filter(user=request.user).exists(),
    })


def is_student(user):
    """Eingeloggt und kein Firmenkonto (#66). Nur Studierende merken Stellen (#13)."""
    return user.is_authenticated and not hasattr(user, "company_member")


@login_required
@require_POST
def job_save(request, pk):
    """„Merken“ an- und wieder abschalten (#13), danach zurück auf ?next= oder ins Stellendetail."""
    if not is_student(request.user):
        raise PermissionDenied("Nur Studierende können Stellen merken.")
    posting = get_object_or_404(JobPosting, pk=pk)
    saved, created = SavedPosting.objects.get_or_create(user=request.user, posting=posting)
    if not created:
        saved.delete()
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect("job_detail", pk=posting.pk)


@login_required
def saved_list(request):
    """Seite „Gemerkt“ (#13): die eigenen gemerkten Stellen, zuletzt gemerkte zuerst."""
    if not is_student(request.user):
        raise PermissionDenied("Nur Studierende können Stellen merken.")
    saved = (
        request.user.saved_postings.select_related("posting__company")
        .prefetch_related("posting__shifts")
        .order_by("-created_at")
    )
    postings = [entry.posting for entry in saved]
    # Lohn und Passung wie in der Stellenliste.
    profile = StudentProfile.objects.filter(user=request.user).first()
    if profile:
        apply_home_commutes(profile, postings)
        lectures = list(profile.lectures.all())
        for posting in postings:
            posting.fit = posting_fit(posting, lectures)
    return render(request, "jobs/saved_list.html", {"postings": postings})


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

    # Anreisedauer nur, wenn gewählt, und nur aus der Datenbank: Die Seite fragt die API
    # nie selbst, damit sie sofort da ist (#74). Fehlende Zeiten der nächsten Stellen
    # holt die Seite per JavaScript über job_map_travel nach (travel_url).
    # Stellen mit Minuten zuerst (nach Minuten), dann alle übrigen nach Luftlinie.
    travel_hint = ""
    travel_url = ""
    if by_travel:
        times = cached_travel_times(start, nearby)
        for posting in nearby:
            posting.travel_minutes = times.get(posting.id)
        missing = [posting.id for posting in nearby[:MAX_TRAVEL_REQUESTS] if posting.id not in times]
        nearby.sort(key=lambda posting: (
            posting.travel_minutes is None,
            posting.travel_minutes or 0,
            posting.distance_km,
            posting.title,
        ))
        if missing:
            travel_hint = "Anreisedauer fehlt noch für einige Stellen, diese nach Luftlinie."
            travel_url = with_query(reverse("job_map_travel"), [
                ("lat", start[0]), ("lon", start[1]), ("stellen", ",".join(str(id) for id in missing)),
            ])

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
        "travel_url": travel_url,
        "max_travel_requests": MAX_TRAVEL_REQUESTS,
        "filter_query": filter_query,
        "start": {"lat": start[0], "lon": start[1]},
        "has_start": bool(start_params),
        "markers": markers,
    })


def job_map_travel(request):
    """JSON für die Karte: Anreise vom Startpunkt (?lat=...&lon=...) zu den Stellen
    ?stellen=1,2,3 (höchstens MAX_TRAVEL_REQUESTS), fehlende von der API (#74).

    Antwort {"Stellen-ID": Minuten}, nur Stellen mit Verbindung. Hält das Zeitbudget
    aus jobs/travel.py ein; was bis dahin fehlt, fehlt auch in der Antwort.
    """
    start = parse_start(request.GET.get("lat"), request.GET.get("lon"))
    if start is None:
        return JsonResponse({"fehler": "Startpunkt lat/lon fehlt oder ist ungültig."}, status=400)
    ids = [part for part in request.GET.get("stellen", "").split(",") if part.isdigit()]
    postings = JobPosting.objects.filter(
        pk__in=ids[:MAX_TRAVEL_REQUESTS], latitude__isnull=False, longitude__isnull=False
    )
    times = fetch_travel_times(start, list(postings))
    return JsonResponse({str(id): minutes for id, minutes in times.items() if minutes is not None})


def fair_list(request):
    """Kommende Messen und Events nach Datum, mit Firmen und deren Stellen (#33)."""
    companies = Company.objects.order_by("name").prefetch_related(
        Prefetch("postings", queryset=JobPosting.objects.order_by("title"))
    )
    fairs = (
        Fair.objects.filter(date__gte=timezone.localdate())
        .order_by("date", "name")
        .prefetch_related(Prefetch("companies", queryset=companies))
    )
    attending = set()
    if request.user.is_authenticated:
        attending = set(request.user.fairs.values_list("pk", flat=True))
    return render(request, "jobs/fair_list.html", {"fairs": fairs, "attending": attending})


@login_required
@require_POST
def fair_attend(request, pk):
    """„Ich gehe hin“ an- und wieder abschalten."""
    fair = get_object_or_404(Fair, pk=pk)
    if fair.visitors.filter(pk=request.user.pk).exists():
        fair.visitors.remove(request.user)
    else:
        fair.visitors.add(request.user)
    return redirect(f"{reverse('fair_list')}#messe-{fair.pk}")
