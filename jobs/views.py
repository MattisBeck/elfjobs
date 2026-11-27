from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, render

from .models import JobPosting

# Filter-Chips der Stellenliste: GET-Parameter "filter", mehrere kombinierbar.
FILTER_CHIPS = {
    "werkstudent": "Werkstudent",
    "kurzjob": "Kurzjob",
    "remote": "Remote",
}


def job_list(request):
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

    chips = []
    for key, label in FILTER_CHIPS.items():
        toggled = [f for f in active if f != key] if key in active else active + [key]
        query = urlencode([("filter", f) for f in toggled])
        chips.append({
            "label": label,
            "active": key in active,
            "url": f"{request.path}?{query}" if query else request.path,
        })

    return render(request, "jobs/job_list.html", {"postings": postings, "chips": chips})


def job_detail(request, pk):
    posting = get_object_or_404(JobPosting.objects.select_related("company"), pk=pk)
    return render(request, "jobs/job_detail.html", {"posting": posting})
