"""Sphinx configuration for MapMyCells2CL documentation."""

from __future__ import annotations

project = "MapMyCells2CL"
author = "Cellular Semantics"
copyright = "2026, Cellular Semantics"  # noqa: A001

extensions = [
    "autoapi.extension",
    "myst_parser",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
]

# AutoAPI — generate API reference from source
autoapi_dirs = ["../src"]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]
autoapi_member_order = "bysource"
autoapi_keep_files = True
autoapi_python_class_content = "class"
suppress_warnings = [
    "autoapi.python_import_resolution",
    # AutoAPI double-documents frozen dataclass fields (class attr + __init__ param)
    "ref.duplicate",
    # AutoAPI generates pages outside the normal source tree; toctree checker
    # can't resolve them as source documents — the HTML is generated correctly
    "toc.not_readable",
    "ref.doc",
]

# Napoleon — Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False

# MyST — Markdown support
myst_enable_extensions = ["colon_fence"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

html_theme = "furo"
html_title = "MapMyCells2CL"

exclude_patterns = ["_build"]
