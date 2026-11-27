from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["profile", "posting", "applied_at", "status"]
    list_filter = ["status", "applied_at"]
    list_select_related = ["profile__user", "posting"]
