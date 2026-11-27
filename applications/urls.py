from django.urls import path

from . import views

urlpatterns = [
    path("jobs/<int:pk>/bewerben/", views.apply, name="apply"),
]
