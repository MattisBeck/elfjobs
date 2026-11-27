from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect

from accounts.models import StudentProfile
from companies.models import CompanyMember
from jobs.models import JobPosting

from .models import Application


@login_required
def apply(request, pk):
    """„Mit Profil bewerben“ (#14).

    Nur ein POST legt die Bewerbung an. Ein GET (z. B. nach dem Login) führt nur zurück zur Stelle.
    """
    posting = get_object_or_404(JobPosting, pk=pk)
    if CompanyMember.objects.filter(user=request.user).exists():
        raise PermissionDenied("Firmenkonten können sich nicht bewerben.")
    if request.method == "POST":
        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        # get_or_create: Ein zweiter Klick legt keine zweite Bewerbung an.
        application, created = Application.objects.get_or_create(profile=profile, posting=posting)
        if created:
            application.attach_cv()  # Lebenslauf mitschicken (#38)
    return redirect("job_detail", pk=posting.pk)


@login_required
def sent_cv(request, pk):
    """Der mit einer Bewerbung gesendete Lebenslauf (#38). Nur für die Bewerberin selbst und Admins."""
    application = get_object_or_404(Application, pk=pk)
    is_owner = application.profile.user_id == request.user.id
    if not (is_owner or request.user.is_staff) or not application.cv:
        raise Http404("Kein Lebenslauf.")
    return FileResponse(application.cv.open("rb"), content_type="application/pdf", filename="lebenslauf.pdf")
