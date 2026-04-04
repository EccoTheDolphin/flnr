# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys

project = "flnr"
copyright = "2026, Anatoly Parshintsev"
author = "Anatoly Parshintsev"
release = "0.0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
]

intersphinx_mapping = {"python": ("https://docs.python.org/3/", None)}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"

autodoc_default_options = {
    "member-order": "bysource",
    "members": True,
}

autodoc_typehints = "description"
autodoc_preserve_defaults = True
add_module_names = False
python_use_unqualified_type_names = True
autosummary_generate = True
nitpicky = False

sys.path.insert(0, os.path.abspath("../src"))
