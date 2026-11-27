from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="job_list"), name="home"),
    path("jobs/", include("jobs.urls")),
    path("", include("accounts.urls")),
    path("", include("timetable.urls")),
    path("admin/", admin.site.urls),
]
