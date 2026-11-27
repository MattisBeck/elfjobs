from django.urls import path

from . import views

urlpatterns = [
    path("firmen/<int:pk>/bewerten/", views.review_company, name="review_company"),
]
