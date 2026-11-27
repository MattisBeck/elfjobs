from django.contrib import admin

from .models import CompanyMember


@admin.register(CompanyMember)
class CompanyMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "company"]
    search_fields = ["user__username", "company__name"]
