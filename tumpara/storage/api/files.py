import graphene
from django.core import signing
from django.urls import reverse as reverse_url
from graphene import relay

from tumpara.api.util import convert_model_field

from .. import models


# For the API, we abstract the concept of file handlers away. The only thing
# libraries contain for clients are objects of type 'File'. This type corresponds to
# the FileHandler model type, but in the API those the concepts of the file and the
# handler are identical.
class FileHandler(relay.Node):
    file_path = convert_model_field(models.File, "path")

    file_url = graphene.String(
        description="Download URL for the original file. This link will be valid for "
        "one hour."
    )

    class Meta:
        name = "File"

    @staticmethod
    def resolve_file_path(obj: models.FileHandler, info: graphene.ResolveInfo) -> str:
        # We used to assert that the object provided here actually is a file handler.
        # Now we also have handler-like objects (AutodevelopedPhoto in the gallery app),
        # which don't explicitly extend FileHandler. So we just resort to duck typing
        # here.
        return obj.file.path

    @staticmethod
    def resolve_file_url(obj: models.FileHandler, info: graphene.ResolveInfo):
        signed_primary_key = signing.dumps(str(obj.file.pk), compress=True)
        return reverse_url("storage_file_download", args=(signed_primary_key,))
