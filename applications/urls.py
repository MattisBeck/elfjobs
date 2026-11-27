from django.urls import path

from . import views

urlpatterns = [
    path("jobs/<int:pk>/bewerben/", views.apply, name="apply"),
    path("jobs/<int:pk>/bewerben/vorschlag/", views.apply_suggest, name="apply_suggest"),
    path("jobs/<int:pk>/bewerben/schicht/", views.apply_shift_add, name="apply_shift_add"),
    path("jobs/<int:pk>/bewerben/schicht/<int:shift_pk>/entfernen/", views.apply_shift_delete, name="apply_shift_delete"),
    path("bewerbungen/<int:pk>/lebenslauf.pdf", views.sent_cv, name="sent_cv"),
]
