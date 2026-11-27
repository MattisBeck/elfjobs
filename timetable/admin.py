from django.contrib import admin

from .models import LectureSlot, PlannedShift


@admin.register(LectureSlot)
class LectureSlotAdmin(admin.ModelAdmin):
    list_display = ("profile", "weekday", "start", "end", "title")
    list_filter = ("weekday",)


@admin.register(PlannedShift)
class PlannedShiftAdmin(admin.ModelAdmin):
    list_display = ("profile", "posting", "weekday", "start", "end")
    list_filter = ("weekday",)
