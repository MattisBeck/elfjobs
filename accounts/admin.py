from django.contrib import admin

from .models import ProfileSkill, StudentProfile


class ProfileSkillInline(admin.TabularInline):
    model = ProfileSkill
    extra = 0


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    inlines = [ProfileSkillInline]
    list_display = ("user", "study_program", "semester", "home_town")
    filter_horizontal = ("courses",)
    # Das Datei-Feld würde auf /media/ verlinken, das gibt es absichtlich nicht (#38).
    exclude = ("cv_file",)
