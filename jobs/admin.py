from django.contrib import admin

from .models import Company, Fair, JobPosting, SavedPosting, Shift, Tag


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "has_logo")

    @admin.display(boolean=True, description="Logo")
    def has_logo(self, company):
        return bool(company.logo_url)


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
    fieldsets = [
        (None, {"fields": [
            "company", "title", "description", "kind", "workplace", "schedule",
            "hourly_wage", "hours_per_week", "tags",
        ]}),
        ("Ort", {"fields": ["address", ("latitude", "longitude")]}),
    ]


@admin.register(SavedPosting)
class SavedPostingAdmin(admin.ModelAdmin):
    list_display = ("user", "posting", "created_at")
