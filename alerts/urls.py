from django.urls import path

from . import views

urlpatterns = [
    path("", views.alert_list, name="alert_list"),
    path("neu/", views.alert_create, name="alert_create"),
    path("<int:pk>/ansehen/", views.alert_view, name="alert_view"),
    path("<int:pk>/loeschen/", views.alert_delete, name="alert_delete"),
]
