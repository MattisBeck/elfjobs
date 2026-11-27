from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["profile", "posting", "applied_at", "status"]
    list_filter = ["status", "applied_at"]
    list_select_related = ["profile__user", "posting"]
    # Das Datei-Feld würde auf /media/ verlinken. Stattdessen ein Link auf die geschützte View (#38).
    exclude = ["cv"]
    readonly_fields = ["cv_link"]

    @admin.display(description="Lebenslauf")
    def cv_link(self, application):
        if not application.cv:
            return "Ohne Lebenslauf gesendet"
        return format_html('<a href="{}" target="_blank">Lebenslauf ansehen (PDF)</a>', reverse("sent_cv", args=[application.pk]))
