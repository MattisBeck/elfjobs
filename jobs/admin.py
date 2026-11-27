from django.contrib import admin

from .models import Company, Fair, JobPosting, Tag


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    pass


@admin.register(Fair)
class FairAdmin(admin.ModelAdmin):
    pass


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    pass


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "kind", "workplace", "schedule", "hourly_wage")
    list_filter = ("kind", "workplace", "schedule")
