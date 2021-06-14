import graphene
from graphene import relay

from tumpara.api.util import convert_model_field

from .. import models


# For the API, we abstract the concept of file handlers away. The only thing
# libraries contain for clients are objects of type 'File'. This type corresponds to
# the FileHandler model type, but in the API those the concepts of the file and the
# handler are identical.
class FileHandler(relay.Node):
    file_path = convert_model_field(models.File, "path")

    class Meta:
        name = "File"

    @staticmethod
    def resolve_file_path(
        parent: models.FileHandler, info: graphene.ResolveInfo
    ) -> str:
        assert isinstance(parent, models.FileHandler)
        return parent.file.path
