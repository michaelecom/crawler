# Configuration file for the Sphinx documentation builder.
# Enterprise Web Crawler Documentation

import os
import sys
from datetime import datetime

# Path setup
sys.path.insert(0, os.path.abspath('..'))

# Project information
project = 'Enterprise Web Crawler'
copyright = f'{datetime.now().year}, Enterprise Web Crawler Team'
author = 'Enterprise Web Crawler Team'
release = '1.0.0-alpha'
version = '1.0.0'

# General configuration
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.ifconfig',
    'sphinx.ext.githubpages',
    'myst_parser',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# Source file suffix
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# Master document
master_doc = 'index'

# Language
language = 'ru'

# HTML output options
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_title = f'{project} Documentation'
html_short_title = 'Crawler Docs'
html_logo = None  # Add logo if available
html_favicon = None  # Add favicon if available

html_theme_options = {
    'navigation_depth': 4,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'includehidden': True,
    'titles_only': False,
    'display_version': True,
}

# Autodoc configuration
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__',
    'show-inheritance': True,
}

# Napoleon settings (Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'aiohttp': ('https://docs.aiohttp.org/en/stable/', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org/en/20/', None),
}

# Todo extension
todo_include_todos = True

# MyST Markdown parser settings
myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'dollarmath',
    'html_image',
    'linkify',
    'replacements',
    'smartquotes',
    'substitution',
    'tasklist',
]
