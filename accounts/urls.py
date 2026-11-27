from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
    path("anmelden/", auth_views.LoginView.as_view(authentication_form=LoginForm), name="login"),
    path("abmelden/", auth_views.LogoutView.as_view(), name="logout"),
    path("registrieren/", views.signup, name="signup"),
    path("registrieren/bestaetigen/", views.confirm_pending, name="confirm_pending"),
    path("konto/bestaetigen/<str:uidb64>/<str:token>/", views.confirm_email, name="confirm_email"),
    path("profil/", views.profile, name="profile"),
    path("willkommen/", views.onboarding_skills, name="onboarding_skills"),
    path("willkommen/stundenplan/", views.onboarding_timetable, name="onboarding_timetable"),
    path("willkommen/jobart/", views.onboarding_kinds, name="onboarding_kinds"),
    path("profil/lebenslauf/", views.cv_select, name="cv_select"),
    path("profil/lebenslauf/hochladen/", views.cv_upload, name="cv_upload"),
    path("profil/lebenslauf/loeschen/", views.cv_delete, name="cv_delete"),
    path("profil/lebenslauf/uebernehmen/", views.cv_accept, name="cv_accept"),
    path("profil/lebenslauf.pdf", views.cv_pdf, name="cv_pdf"),
]
