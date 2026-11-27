from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "elfjobs"
admin.site.site_title = "elfjobs"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="job_list"), name="home"),
    path("jobs/", include("jobs.urls")),
    path("", include("applications.urls")),
    path("firma/", include("companies.urls")),
    path("alerts/", include("alerts.urls")),
    path("", include("accounts.urls")),
    path("", include("timetable.urls")),
    path("admin/", admin.site.urls),
]

# Hochgeladene Logos (#73) ausliefern, nur bei DEBUG (static() gibt sonst nichts zurück).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
