from .matching import new_postings


def new_matches(request):
    """Anzahl neuer passender Stellen aus allen Alerts für den Hinweis in der Kopfzeile (#34)."""
    if not request.user.is_authenticated:
        return {}
    return {"alert_new_count": sum(len(new_postings(alert)) for alert in request.user.job_alerts.all())}
