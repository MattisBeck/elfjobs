from django.urls import path

from . import views

urlpatterns = [
    path("stundenplan/", views.timetable, name="timetable"),
    path("stundenplan/<int:pk>/", views.lecture_edit, name="lecture_edit"),
    path("stundenplan/<int:pk>/loeschen/", views.lecture_delete, name="lecture_delete"),
]
