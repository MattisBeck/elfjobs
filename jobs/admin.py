from django.contrib import admin

from .models import Company, Fair, JobPosting, Shift, Tag


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    pass


@admin.register(Fair)
class FairAdmin(admin.ModelAdmin):
    pass


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    pass


class ShiftInline(admin.TabularInline):
    model = Shift
    extra = 0


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    inlines = [ShiftInline]
    list_display = ("title", "company", "kind", "workplace", "schedule", "hourly_wage")
    list_filter = ("kind", "workplace", "schedule")
