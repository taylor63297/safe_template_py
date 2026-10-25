# safe_template_py

A template renderer that substitutes `{{ name }}` placeholders from a mapping and cannot execute anything — no expressions, no attribute access, no filters, no control flow.

## Usage

```python
from safe_template_py import SafeTemplate, render_string, MissingVariable

# One-shot convenience:
render_string("Hello, {{ name }}!", {"name": "world"})
# -> "Hello, world!"

# Compile once, render many times with a missing-variable policy:
tpl = SafeTemplate("{{ greeting }}, {{ name }}!", missing=SafeTemplate.KEEP)
tpl.render({"name": "world"})
# -> "{{ greeting }}, world!"
```

Exported names: `SafeTemplate`, `render_string`, `SafeTemplateError`, `MissingVariable`.

## Why this exists

The problem: you have an untrusted template string and a dictionary of values, and you need to produce text. Standard formatters (`str.format`, `string.Template`) either execute format specs that can call `__format__` on objects, or are too permissive about what counts as a substitution. This library restricts substitutions to bare identifiers inside `{{ }}` and stringifies values with `str()` — nothing more.

The trade-off: there is no expression evaluation, no attribute access, and no default value syntax. If you need `{{ user.name }}`, you must flatten your data first: `{"user_name": user.name}`. This is deliberate. A template engine that supports attribute paths is one regular expression away from one that supports method calls.

## Edge cases you will hit

- `{{ a.b }}` raises `SyntaxError` at parse time, not at render time. The library fails loud rather than emitting the token as literal text, because a silently-passthrough bad token looks correct in a quick glance but produces broken output.
- `{{ }}` (whitespace-only braces) is also a `SyntaxError`. An empty name cannot be a mapping key.
- `None` values render as the string `"None"` — `str(None)`. The library does not special-case `None` because doing so would hide missing data that happens to be explicitly `None`.
- By default, a missing variable raises `MissingVariable`. Pass `missing=SafeTemplate.KEEP` to leave the token verbatim, `missing=SafeTemplate.BLANK` for an empty string, or any `callable` taking the name and returning a string.
