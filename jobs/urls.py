from django.urls import path

from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("karte/", views.job_map, name="job_map"),
    path("karte/anreise.json", views.job_map_travel, name="job_map_travel"),
    path("<int:pk>/", views.job_detail, name="job_detail"),
]
