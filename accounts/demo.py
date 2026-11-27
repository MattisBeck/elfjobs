"""Demo-Login (#148): Anmelden ohne Passwort, nur für Vorführungen (Einstellung DEMO_LOGIN)."""

from django.contrib.auth.models import User

MIA_EMAIL = "mia@student.hpi.uni-potsdam.de"


def demo_users(kind):
    """Konten, die der Demo-Login anbietet. Staff und Superuser sind nie dabei."""
    users = User.objects.filter(is_active=True, is_staff=False, is_superuser=False)
    if kind == "student":
        users = users.filter(profile__isnull=False, company_member__isnull=True).order_by("username")
        # Mia zuerst, dann der Rest nach Benutzername.
        mia = [u for u in users if u.email == MIA_EMAIL]
        return mia + [u for u in users if u.email != MIA_EMAIL]
    if kind == "company":
        users = users.filter(company_member__isnull=False).select_related("company_member__company")
        return list(users.order_by("company_member__company__name", "username"))
    return []


def demo_label(user, kind):
    if kind == "company":
        return f"{user.company_member.company.name} – {user.email}"
    return f"{user.get_full_name() or user.username} – {user.email}"
