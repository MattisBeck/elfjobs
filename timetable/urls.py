from django.urls import path

from . import views

urlpatterns = [
    path("stundenplan/", views.timetable, name="timetable"),
    path("stundenplan/<int:pk>/", views.lecture_edit, name="lecture_edit"),
    path("stundenplan/import/", views.ics_upload, name="ics_upload"),
    path("stundenplan/import/vorschau/", views.ics_preview, name="ics_preview"),
    path("stundenplan/<int:pk>/loeschen/", views.lecture_delete, name="lecture_delete"),
]
