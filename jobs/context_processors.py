from .views import is_student


def saved_count(request):
    """Zähler „Gemerkt · 2“ in der Navigation (#13), nur für eingeloggte Studierende."""
    if not is_student(request.user):
        return {}
    return {"saved_count": request.user.saved_postings.count()}
