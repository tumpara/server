from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import *

admin.site.register(User, UserAdmin)


class UserMembershipInline(GenericTabularInline):
    model = UserMembership
