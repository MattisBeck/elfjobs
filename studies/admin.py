from django.contrib import admin

from .models import Course, StudyProgram


class CourseInline(admin.TabularInline):
    model = Course
    extra = 0
    filter_horizontal = ("skills",)


@admin.register(StudyProgram)
class StudyProgramAdmin(admin.ModelAdmin):
    inlines = [CourseInline]
    list_display = ("name", "abbreviation", "university", "standard_semesters")
