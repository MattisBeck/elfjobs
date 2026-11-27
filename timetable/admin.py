from django.contrib import admin

from .models import LectureSlot


@admin.register(LectureSlot)
class LectureSlotAdmin(admin.ModelAdmin):
    list_display = ("profile", "weekday", "start", "end", "title")
    list_filter = ("weekday",)
