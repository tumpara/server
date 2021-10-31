from tumpara.api import Subschema

from . import filtersets  # noqa: F401 (this import has side effects)
from . import Photo

subschema = Subschema(types=[Photo])
