from django.urls import path

from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("karte/", views.job_map, name="job_map"),
    path("karte/anreise.json", views.job_map_travel, name="job_map_travel"),
    path("<int:pk>/", views.job_detail, name="job_detail"),
    path("messen/", views.fair_list, name="fair_list"),
    path("messen/<int:pk>/hingehen/", views.fair_attend, name="fair_attend"),
]
