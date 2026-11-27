from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .matching import alert_label, new_postings
from .models import JobAlert


@login_required
def alert_list(request):
    alerts = list(request.user.job_alerts.all())
    for alert in alerts:
        alert.new_count = len(new_postings(alert))
    return render(request, "alerts/alert_list.html", {"alerts": alerts})


@login_required
@require_POST
def alert_create(request):
    """Aktuelle Filter der Stellenliste als Alert speichern."""
    query = request.POST.get("query", "")[:500]
    JobAlert.objects.create(user=request.user, query=query, label=alert_label(query))
    messages.success(request, "Alert gespeichert. Neue passende Stellen siehst du oben in der Kopfzeile.")
    return redirect("alert_list")


@login_required
@require_POST
def alert_view(request, pk):
    """Als angesehen markieren und die Stellenliste mit den Filtern des Alerts öffnen."""
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.last_seen_at = timezone.now()
    alert.save(update_fields=["last_seen_at"])
    url = reverse("job_list")
    return redirect(f"{url}?{alert.query}" if alert.query else url)


@login_required
@require_POST
def alert_delete(request, pk):
    get_object_or_404(JobAlert, pk=pk, user=request.user).delete()
    messages.success(request, "Alert gelöscht.")
    return redirect("alert_list")
