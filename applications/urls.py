from django.urls import path

from . import views

urlpatterns = [
    path("jobs/<int:pk>/bewerben/", views.apply, name="apply"),
    path("bewerbungen/<int:pk>/lebenslauf.pdf", views.sent_cv, name="sent_cv"),
]
