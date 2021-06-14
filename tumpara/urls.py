from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView

import tumpara.multimedia.views
import tumpara.timeline.models

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
        tumpara.multimedia.views.preview_image,
        name="multimedia_preview_image",
    ),
]
