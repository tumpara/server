# Documentation config file, built with sphinx-quickstart.
#
# See here for a complete reference:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import inspect
import sys
from os import environ
from pathlib import Path

import django
import django.db.models
from django.utils.encoding import force_str
from django.utils.html import strip_tags
from pygments_graphql import GraphqlLexer

# Make sure we are documenting the actual code and not some other potentially installed
# version of the app.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup the Django app so that we can document models.
environ.setdefault("DJANGO_SETTINGS_MODULE", "tumpara.settings.development")
django.setup()


# -- Project information ---------------------------------------------------------------

project = "Tumpara"
copyright = "2021, Yannik Rödel"
author = "Yannik Rödel"


# -- Other Sphinx configuration --------------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx_rtd_theme",
]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"


# -- Compile hooks ---------------------------------------------------------------------


def process_docstring(app, what, name, obj, options, lines):
    # Add a parameter docstring for every Django field. This is taken (in part) from
    # here: https://djangosnippets.org/snippets/2533/
    if inspect.isclass(obj) and issubclass(obj, django.db.models.Model):
        for field in obj._meta.fields:
            help_text = strip_tags(force_str(field.help_text))
            verbose_name = force_str(field.verbose_name).capitalize()

            # Add the model field to the end of the docstring so that it is documented.
            # This will use either the help text or the verbose name.
            lines.append(
                f":param {field.attname}: {help_text if help_text else verbose_name}"
            )
            lines.append(f":type {field.attname}: {type(field).__name__}")

    return lines


def setup(app):
    app.add_lexer("graphql", GraphqlLexer)
    app.connect("autodoc-process-docstring", process_docstring)
