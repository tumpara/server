from django.contrib import admin

from tumpara.accounts.admin import UserMembershipInline

from .models import *


class EntryInlineAdmin(admin.TabularInline):
    model = Entry


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "location", "visibility")
    search_fields = ("pk",)


@admin.register(Album)
class CollectionAdmin(admin.ModelAdmin):
    inlines = (UserMembershipInline,)
    list_display = ("name",)
    search_fields = ("name",)
