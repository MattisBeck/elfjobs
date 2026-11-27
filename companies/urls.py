from django.urls import path

from . import views

urlpatterns = [
    path("", views.company_home, name="company_home"),
    path("registrieren/", views.company_signup, name="company_signup"),
    path("anmelden/", views.company_login, name="company_login"),
    path("stellen/neu/", views.posting_edit, name="company_posting_new"),
    path("stellen/<int:pk>/", views.posting_edit, name="company_posting_edit"),
]
