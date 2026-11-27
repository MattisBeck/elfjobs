"""Durchschnitt und Anzahl der Bewertungen je Firma (#32) für Stellenliste und Stellendetail."""

from django.db.models import Avg, Count

from applications.models import Application

from .forms import ReviewForm
from .models import Review


def company_ratings():
    """{Firmen-ID: {"average": 4.5, "count": 2}} für alle Firmen mit Bewertungen, eine Abfrage."""
    rows = Review.objects.values("company").annotate(average=Avg("stars"), count=Count("id")).order_by()
    return {row["company"]: {"average": row["average"], "count": row["count"]} for row in rows}


def attach_ratings(postings):
    """Setzt posting.rating (siehe company_ratings) oder None, wenn die Firma noch keine Bewertung hat."""
    ratings = company_ratings()
    for posting in postings:
        posting.rating = ratings.get(posting.company_id)


def rating_key(posting):
    """Sortierung „Bewertung“: Durchschnitt, dann Anzahl, dann effektiver Lohn und Titel.
    Firmen ohne Bewertung kommen ans Ende."""
    rating = posting.rating
    if rating is None:
        return (1, 0, 0, -posting.effective_wage, posting.title)
    return (0, -rating["average"], -rating["count"], -posting.effective_wage, posting.title)


def can_review(profile, company):
    """Bewerten darf, wer sich auf irgendeine Stelle der Firma beworben hat."""
    return profile is not None and Application.objects.filter(profile=profile, posting__company=company).exists()


def review_context(profile, company):
    """Daten für den Abschnitt „Bewertungen“ im Stellendetail."""
    reviews = list(company.reviews.all())
    allowed = can_review(profile, company)
    own = next((review for review in reviews if review.profile_id == profile.id), None) if profile else None
    return {
        "company": company,
        "reviews": reviews,
        "average": sum(review.stars for review in reviews) / len(reviews) if reviews else None,
        "count": len(reviews),
        "own": own,
        "form": ReviewForm(instance=own) if allowed else None,
    }
