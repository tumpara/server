from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView

from tumpara.multimedia import views as multimedia_views
from tumpara.storage import views as storage_views

urlpatterns = [
    path("admin/", admin.site.urls, name="admin"),
    path(
        "api/graphql",
        csrf_exempt(
            GraphQLView.as_view(
                graphiql=settings.GRAPHENE["GRAPHIQL"]
                if "GRAPHIQL" in settings.GRAPHENE
                else settings.DEBUG
            )
        ),
    ),
    path(
        "api/preview-image/<description>",
        multimedia_views.preview_image,
        name="multimedia_preview_image",
    ),
    path(
        "api/file/<primary_key>",
        storage_views.file_download,
        name="storage_file_download",
    ),
]
