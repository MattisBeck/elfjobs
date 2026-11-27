from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import StudentProfile
from jobs.models import Company

from .forms import ReviewForm
from .models import Review
from .ratings import can_review


@login_required
@require_POST
def review_company(request, pk):
    """Firma bewerten (#32). Nur mit Bewerbung; ein zweites Absenden ändert die eigene Bewertung."""
    company = get_object_or_404(Company, pk=pk)
    profile = StudentProfile.objects.filter(user=request.user).first()
    if not can_review(profile, company):
        raise PermissionDenied("Bewerten kann nur, wer sich bei der Firma beworben hat.")

    own = Review.objects.filter(profile=profile, company=company).first()
    form = ReviewForm(request.POST, instance=own)
    if form.is_valid():
        review = form.save(commit=False)
        review.profile = profile
        review.company = company
        review.save()
        messages.success(request, "Danke für deine Bewertung.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)

    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect("job_list")
