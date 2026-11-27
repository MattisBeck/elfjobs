from django.urls import path

from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("karte/", views.job_map, name="job_map"),
    path("karte/anreise.json", views.job_map_travel, name="job_map_travel"),
    path("<int:pk>/", views.job_detail, name="job_detail"),
    path("<int:pk>/schichten/", views.planned_shift_add, name="planned_shift_add"),
    path("<int:pk>/schichten/<int:shift_pk>/loeschen/", views.planned_shift_delete, name="planned_shift_delete"),
    path("<int:pk>/merken/", views.job_save, name="job_save"),
    path("gemerkt/", views.saved_list, name="saved_list"),
    path("messen/", views.fair_list, name="fair_list"),
    path("messen/<int:pk>/hingehen/", views.fair_attend, name="fair_attend"),
]
