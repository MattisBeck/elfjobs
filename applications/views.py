from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect

from accounts.models import StudentProfile
from companies.models import CompanyMember
from jobs.models import JobPosting

from .models import Application
from .quota import applications_left


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
        already_applied = Application.objects.filter(profile=profile, posting=posting).exists()
        # Freemium (#62): Ist das Wochenkontingent aufgebraucht, entsteht keine neue Bewerbung.
        # Das Stellendetail zeigt dann den deaktivierten Knopf mit dem Hinweis.
        if not already_applied and applications_left(profile) > 0:
            # get_or_create: Ein zweiter Klick legt keine zweite Bewerbung an.
            Application.objects.get_or_create(profile=profile, posting=posting)
    return redirect("job_detail", pk=posting.pk)
