from django.contrib import admin

from .models import *


@admin.register(RawPhoto)
class RawPhotoAdmin(admin.ModelAdmin):
    list_display = (
        "file",
        "metadata_digest",
    )
    search_fields = (
        "pk",
        "file__path",
    )


@admin.register(Photo)
@admin.register(AutodevelopedPhoto)
class PhotoAdmin(admin.ModelAdmin):
    list_display = (
        "file",
        "timestamp",
        "size",
        "camera_name",
    )
    search_fields = (
        "pk",
        "file__path",
    )

    @staticmethod
    def size(obj: Photo):
        return f"{obj.width} × {obj.height}"
