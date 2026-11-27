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
    path("profil/lebenslauf/", views.cv_select, name="cv_select"),
    path("profil/lebenslauf/uebernehmen/", views.cv_accept, name="cv_accept"),
    path("profil/lebenslauf.pdf", views.cv_pdf, name="cv_pdf"),
]
