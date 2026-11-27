from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["company", "stars", "profile", "updated_at"]
    list_filter = ["stars"]
    list_select_related = ["company", "profile__user"]
