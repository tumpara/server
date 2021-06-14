from tumpara.api import Subschema

from . import filtersets  # Import side effects
from . import Photo

subschema = Subschema(types=[Photo])
