"""Core implementation of the safe template renderer.

Design decisions, stated plainly so the tests and the reader share one model:

1.  The ONLY substitution token is ``{{ name }}``.  No ``{% if %}``, no
    ``{{ a.b }}`` attribute access, no filters, no inheritance.  Every feature
    removed is a feature that cannot be abused.  The renderer's whole purpose
    is to be provably unable to call a function, import a module, or touch an
    attribute path.

2.  A name matches ``[A-Za-z_][A-Za-z0-9_]*``.  Whitespace inside the braces is
    optional and stripped, so ``{{name}}``, ``{{ name }}`` and ``{{\t name\t}}``
    are identical.  Anything else inside braces — ``{{a.b}}``, ``{{a-b}}``,
    ``{{ }}`` — is a ``SyntaxError`` at parse time, NOT silently emitted as
    literal text.  Failing loud at parse time is how a template author learns
    that attribute access is not supported, rather than shipping a template
    that renders the token verbatim and looks fine in a quick glance.

3.  Missing variables raise ``MissingVariable`` by default.  The caller can
    instead pass ``missing=SafeTemplate.KEEP`` to leave the token verbatim, or
    ``missing=SafeTemplate.BLANK`` to substitute an empty string, or any
    callable ``fn(name) -> str`` for custom behaviour.  A bare sentinel string
    like "" would be indistinguishable from a legitimately-empty value, so we
    use real sentinels.

4.  Values are converted with ``str()`` exactly once.  We never call
    ``format()``, never call ``__format__``, never interpolate.  This matters
    because some objects define ``__format__`` to do surprising things; calling
    only ``str()`` keeps the surface minimal.

5.  A ``{{ }}`` token with only whitespace is rejected as a syntax error.  An
    empty name cannot be a key, and accepting it would hide a typo in the
    template.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Union

__all__ = [
    "SafeTemplate",
    "render_string",
    "SafeTemplateError",
    "MissingVariable",
]


class SafeTemplateError(Exception):
    """Base class for all safe_template_py errors."""


class MissingVariable(SafeTemplateError):
    """Raised when a placeholder name is absent from the variables mapping.

    Subclassing SafeTemplateError lets callers catch "any template problem"
    with one except clause while still being able to distinguish missing
    variables from syntax errors when they care.
    """


# A compiled token represents either a literal chunk of text or a named hole.
# Using a small list of tuples keeps the render loop branch-free and avoids
# the overhead of a class hierarchy for two cases.
_Literal = tuple[str, str]       # ("lit", text)
_Variable = tuple[str, str]      # ("var", name)
_Token = Union[_Literal, _Variable]


# Matches exactly ``{{ <name> }}`` where <name> is a python identifier and the
# surrounding whitespace is optional.  We deliberately do NOT allow dots,
# dashes, or spaces in the name itself, so attribute access is impossible by
# construction.
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

# Matches anything that looks like it wanted to be a placeholder but is not a
# valid one — braces containing something other than a single bare identifier.
# This is what lets us reject ``{{a.b}}`` and ``{{ }}`` at parse time instead
# of emitting them as literal text.
_BAD_PLACEHOLDER = re.compile(r"\{\{[^{}]*\}")


class SafeTemplate:
    """Compile a template once, render it many times.

    Example::

        tpl = SafeTemplate("Hello, {{ name }}!")
        tpl.render({"name": "world"})   # -> "Hello, world!"

    Parameters
    ----------
    source:
        The template string.
    missing:
        What to do when a placeholder name is not in the variables mapping.
        One of:
          * ``SafeTemplate.RAISE``  (default) — raise MissingVariable.
          * ``SafeTemplate.KEEP``   — leave the original ``{{ name }}`` text.
          * ``SafeTemplate.BLANK``  — substitute an empty string.
          * any ``Callable[[str], str]`` — call it with the name and use the
            returned string.
    """

    # Sentinels.  We use the class itself as the carrier so that identity
    # checks (``is SafeTemplate.RAISE``) are unambiguous and cannot be fooled
    # by a variable that happens to equal a string the caller passed in.
    RAISE = object()
    KEEP = object()
    BLANK = object()

    def __init__(
        self,
        source: str,
        missing: Union[object, Callable[[str], str]] = None,
    ) -> None:
        if not isinstance(source, str):
            raise TypeError(
                f"template source must be str, got {type(source).__name__}"
            )
        if missing is None:
            missing = SafeTemplate.RAISE
        self._source = source
        self._missing = missing
        self._tokens: list[_Token] = self._parse(source)

    # ------------------------------------------------------------------ parse
    @staticmethod
    def _parse(source: str) -> list[_Token]:
        """Split *source* into an ordered list of literal and variable tokens.

        We walk the valid-placeholder regex and, between matches, scan for
        bad placeholders.  A bad placeholder between two good ones means the
        author wrote something like ``{{a.b}}`` expecting attribute access;
        we raise SyntaxError immediately rather than silently emitting it.
        """
        tokens: list[_Token] = []
        pos = 0
        for m in _PLACEHOLDER.finditer(source):
            # Anything between the previous token and this match is literal
            # text — but first make sure it contains no *bad* placeholders.
            literal_chunk = source[pos:m.start()]
            SafeTemplate._check_no_bad_placeholders(literal_chunk)
            if literal_chunk:
                tokens.append(("lit", literal_chunk))
            tokens.append(("var", m.group(1)))
            pos = m.end()
        # Trailing literal after the last placeholder.
        trailing = source[pos:]
        SafeTemplate._check_no_bad_placeholders(trailing)
        if trailing:
            tokens.append(("lit", trailing))
        return tokens

    @staticmethod
    def _check_no_bad_placeholders(text: str) -> None:
        bad = _BAD_PLACEHOLDER.search(text)
        if bad is not None:
            raise SyntaxError(
                f"invalid placeholder {bad.group(0)!r}: "
                "only '{{ identifier }}' is supported"
            )

    # ---------------------------------------------------------------- render
    def render(self, variables: Mapping[str, Any]) -> str:
        """Render the compiled template with *variables*.

        *variables* must be a mapping; its values are stringified with
        ``str()`` and nothing else.
        """
        if not isinstance(variables, Mapping):  # pragma: no branch
            raise TypeError(
                f"variables must be a mapping, got {type(variables).__name__}"
            )
        parts: list[str] = []
        for kind, value in self._tokens:
            if kind == "lit":
                parts.append(value)
            else:  # "var"
                parts.append(self._resolve(value, variables))
        return "".join(parts)

    def _resolve(self, name: str, variables: Mapping[str, Any]) -> str:
        if name in variables:
            return str(variables[name])
        # name is missing — consult the missing-policy.
        miss = self._missing
        if miss is SafeTemplate.RAISE:
            raise MissingVariable(
                f"placeholder {name!r} not found in variables"
            )
        if miss is SafeTemplate.KEEP:
            return "{{ " + name + " }}"
        if miss is SafeTemplate.BLANK:
            return ""
        if callable(miss):
            return str(miss(name))
        # Should be unreachable unless someone poked at _missing directly.
        raise TypeError(  # pragma: no cover
            f"invalid missing-policy {miss!r}"
        )

    # ----------------------------------------------------------------- dunder
    def __repr__(self) -> str:
        return f"SafeTemplate(source={self._source!r})"


def render_string(
    source: str,
    variables: Mapping[str, Any],
    missing: Union[object, Callable[[str], str]] = None,
) -> str:
    """One-shot convenience: compile *source* and render with *variables*.

    Equivalent to ``SafeTemplate(source, missing=missing).render(variables)``.
    Useful when you only render a template once and do not want to hold the
    compiled object.
    """
    return SafeTemplate(source, missing=missing).render(variables)
