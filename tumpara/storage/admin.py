import logging

from django import http
from django.contrib import admin

from tumpara.accounts.admin import UserMembershipInline

from .models import *

_logger = logging.getLogger(__name__)


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    inlines = (UserMembershipInline,)
    list_display = ("source", "context")
    change_form_template = "library_change_form.html"

    def response_change(self, request, library):
        if "_scan" in request.POST:
            # try:
            #     library.scan()
            #     self.message_user(
            #         request, "Successfully scanned this library for new and updated content."
            #     )
            # except Exception as error:
            #     _logger.error(error)
            #     self.message_user(
            #         request,
            #         "Error while scanning this library. Check the server logs for details.",
            #         messages.ERROR,
            #     )
            library.scan()
            self.message_user(
                request,
                "Successfully scanned this library for new and updated content.",
            )
            return http.HttpResponseRedirect(".")

        return super().response_change(request, library)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("library", "path")
