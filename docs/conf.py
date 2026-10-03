# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from pathlib import Path
from typing import Any

from sphinx.application import Sphinx
from sphinx.ext import apidoc

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = ""
copyright = "2026, mark doerr"
author = "mark doerr"
release = "0.0.5"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "myst_parser",
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.apidoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    #'sphinx.ext.mathjax',
]
napoleon_google_docstring = False

# The suffix of source filenames.
source_suffix = [
    ".rst",
    ".md",
]

# The master toctree document.
master_doc = "index"

# Add any paths that contain templates here, relative to this directory.
templates_path = [
    "_templates",
]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = "furo"
html_theme = "python_docs_theme"

# Theme options are theme-specific and customize the look and feel of a
# theme further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {
#     "logo": "LARA_logo.svg",
#     "show_powered_by": False,
#     "font_family": "sans-serif",
#     "head_font_family": "Lato, sans-serif",
#     "page_width": "1280px",
#     "sidebar_width": "200px",
#     "code_font_size": ".85em",
#     "font_size": ".9em",
#     "link": "hsl(195, 60%, 20%)",
# }

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_logo = "_static/flamecheck_logo.svg"

# -- Automatically run sphinx-apidoc -----------------------------------------


def run_apidoc(_: Any) -> None:
    """Run sphinx-apidoc."""
    docs_path = Path(__file__).parent
    module_path = docs_path.parent / "src" / "flamecheck"

    apidoc.main(
        [
            "--force",
            "--module-first",
            "-o",
            docs_path.as_posix(),
            module_path.as_posix(),
        ]
    )


def setup(app: Sphinx) -> None:
    """Setup sphinx."""
    app.connect("builder-inited", run_apidoc)


# -- Options for LaTeX output ------------------------------------------

latex_elements: dict[str, str] = {
    # The paper size ('letterpaper' or 'a4paper').
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    # 'preamble': '',
    # Latex figure (float) alignment
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto, manual, or own class]).
latex_documents = [
    (master_doc, ".tex", " Documentation", author, "manual"),
]


# -- Options for manual page output ------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "", " Documentation", [author], 1)]


# -- Options for Texinfo output ----------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, "", " Documentation", author, "", "One line description of project.", "Miscellaneous"),
]
