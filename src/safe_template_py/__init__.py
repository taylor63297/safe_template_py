"""safe_template_py — a template renderer that cannot execute anything.

Exports:
    SafeTemplate       — compile-once renderer for {{name}} placeholders.
    render_string      — one-shot convenience wrapper.
    SafeTemplateError  — base exception for all rendering errors.
    MissingVariable    — raised (or used as sentinel) for undefined names.
"""

from .core import (
    SafeTemplate,
    render_string,
    SafeTemplateError,
    MissingVariable,
)

__all__ = [
    "SafeTemplate",
    "render_string",
    "SafeTemplateError",
    "MissingVariable",
]
